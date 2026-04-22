"""Routing-intelligence tool: calls the live Payment Router API (Project 2).

The chatbot exposes `query_routing_intelligence` as a custom tool to Claude.
When the model invokes it, we POST to https://ivanantonov.com/router/recommend
and return the ranked providers as a structured tool_result the model can cite.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("chatbot.routing")

ROUTER_API_URL = os.getenv("ROUTER_API_URL", "https://ivanantonov.com/router/recommend")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
ROUTER_TIMEOUT_SEC = float(os.getenv("ROUTER_TIMEOUT_SEC", "15"))

# Custom tool schema — handed to Claude alongside code_execution.
# Keep parameters small and opinionated so the model fills them reliably.
ROUTING_TOOL_SCHEMA: dict[str, Any] = {
    "name": "query_routing_intelligence",
    "description": (
        "Call the live payment-router simulator to get a ranked list of provider "
        "archetypes for a given transaction profile. Use this when the user asks "
        "WHICH PROVIDER / WHICH ARCHETYPE / WHERE TO ROUTE a payment — e.g. "
        "\"which archetype for a Brazilian Visa at $300?\", \"best acquirer for "
        "India debit cards\", \"route options for a German 3DS transaction\". "
        "Do NOT use this for questions about the historical CSV book — for those "
        "use the code_execution tool with pandas. The router returns provider "
        "archetype names (e.g. regional-card-specialist-a, global-acquirer-b), "
        "projected approval rate, p50/p95 latency, and a short reasoning string."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": "ISO 3166-1 alpha-2 merchant country, e.g. BR, US, DE.",
            },
            "amount": {
                "type": "number",
                "description": "Transaction amount in the given currency. Must be > 0.",
            },
            "currency": {
                "type": "string",
                "description": "ISO 4217 currency code, e.g. USD, EUR, BRL. Defaults to USD.",
                "default": "USD",
            },
            "card_brand": {
                "type": "string",
                "enum": ["visa", "mastercard", "amex", "discover", "jcb", "unionpay"],
                "description": "Card brand. Defaults to visa.",
                "default": "visa",
            },
            "card_type": {
                "type": "string",
                "enum": ["credit", "debit", "prepaid", "commercial"],
                "description": "Card type. Defaults to credit.",
                "default": "credit",
            },
            "issuer_country": {
                "type": "string",
                "description": (
                    "ISO 3166-1 alpha-2 card-issuing country. Omit if unknown or "
                    "assumed domestic. Include only when the user signals "
                    "cross-border (e.g. 'Nigerian card on Brazilian merchant')."
                ),
            },
            "use_3ds": {
                "type": "boolean",
                "description": "True if the transaction should simulate 3DS flow.",
                "default": False,
            },
        },
        "required": ["country", "amount"],
    },
}


def _err(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    """Standardised error payload the model can explain to the user."""
    payload = {"error": True, "error_kind": kind, "error_message": message}
    payload.update(extra)
    return payload


def call_routing_api(args: dict[str, Any]) -> dict[str, Any]:
    """Execute the tool call. Returns a JSON-serialisable dict.

    Never raises — failure paths return structured error dicts so the LLM can
    apologise gracefully instead of the chat stream dying on a 500.
    """
    if not ROUTER_API_KEY:
        return _err(
            "config",
            "Routing API key is not configured on the chatbot server. "
            "Tell the user the routing simulator is temporarily unavailable.",
        )

    # Build request body matching CompareRequest schema on the router side.
    body: dict[str, Any] = {
        "country": str(args.get("country", "")).upper().strip(),
        "amount": float(args.get("amount", 0)),
        "currency": str(args.get("currency", "USD")).upper().strip(),
        "card_brand": str(args.get("card_brand", "visa")).lower().strip(),
        "card_type": str(args.get("card_type", "credit")).lower().strip(),
        "use_3ds": bool(args.get("use_3ds", False)),
    }
    if args.get("issuer_country"):
        body["issuer_country"] = str(args["issuer_country"]).upper().strip()

    headers = {
        "Authorization": f"Bearer {ROUTER_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "payment-chatbot/1.0 (+https://ivanantonov.com/chatbot)",
    }

    try:
        resp = httpx.post(
            ROUTER_API_URL,
            content=json.dumps(body),
            headers=headers,
            timeout=ROUTER_TIMEOUT_SEC,
        )
    except httpx.TimeoutException:
        log.warning("routing api timeout", extra={"body": body})
        return _err(
            "timeout",
            f"The routing simulator did not respond within {ROUTER_TIMEOUT_SEC:.0f}s. "
            "Tell the user to try again; do not fabricate a ranking.",
        )
    except httpx.RequestError as e:
        log.warning("routing api network error: %s", e, extra={"body": body})
        return _err(
            "network",
            f"Could not reach the routing simulator ({e.__class__.__name__}). "
            "Tell the user the routing service is unreachable; do not invent numbers.",
        )

    if resp.status_code == 401:
        log.error("routing api 401 — key rotated or invalid")
        return _err(
            "auth",
            "The chatbot's routing API key was rejected. "
            "Tell the user the routing simulator is temporarily offline — "
            "operator needs to rotate the key.",
            status=401,
        )
    if resp.status_code == 429:
        return _err(
            "rate_limited",
            "Routing simulator rate-limited this request. Ask the user to retry shortly.",
            status=429,
        )
    if resp.status_code >= 500:
        log.warning("routing api 5xx: %s %s", resp.status_code, resp.text[:200])
        return _err(
            "server_error",
            f"Routing simulator returned {resp.status_code}. "
            "Tell the user the simulator is having a problem; do not invent numbers.",
            status=resp.status_code,
        )
    if resp.status_code >= 400:
        # 4xx other than auth/429 — usually validation. Surface the detail.
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        return _err(
            "bad_request",
            f"Routing simulator rejected the request: {detail}",
            status=resp.status_code,
            request=body,
        )

    try:
        data = resp.json()
    except Exception as e:
        return _err("parse", f"Routing simulator returned non-JSON: {e}")

    # Compact the rankings for the LLM — drop noisy decline_code_distribution
    # keys below 5% and round rates. Keeps the tool_result token-efficient.
    rankings = []
    for r in data.get("rankings", []):
        top_declines = {
            code: round(share, 3)
            for code, share in (r.get("decline_code_distribution") or {}).items()
            if share >= 0.05
        }
        rankings.append({
            "provider_archetype": r.get("provider"),
            "approval_rate": round(r.get("projected_approval_rate", 0.0), 3),
            "latency_p50_ms": round(r.get("latency_p50_ms", 0.0)),
            "latency_p95_ms": round(r.get("latency_p95_ms", 0.0)),
            "top_decline_codes": top_declines,
            "three_ds_challenge_rate": (
                round(r["three_ds_challenge_rate"], 3)
                if r.get("three_ds_challenge_rate") is not None else None
            ),
        })

    return {
        "scenario": body,
        "recommended_archetype": data.get("recommended_provider"),
        "reasoning": data.get("reasoning", ""),
        "rankings": rankings,
        "source": "live payment-router simulator (ivanantonov.com/router)",
    }
