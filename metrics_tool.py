"""Deterministic multi-hop metrics tool — the arithmetic backstop.

Pattern P2 in `adversarial_chatbot_report.md`: the LLM fabricates multi-hop
retry/recovery/drop numbers even though the underlying CSV can answer them
exactly. This module exposes a small set of pandas-backed functions the
model calls BEFORE falling back to free-form `code_execution`. Each
function loads the CSV once (cached at module level) and returns a
JSON-serialisable dict the model can cite directly.

Exposed as an Anthropic custom tool via `METRICS_TOOL_SCHEMA` — registered
in `agent.py` alongside `code_execution` and `query_routing_intelligence`.

Design constraints:
- Never raises — failure paths return {"error": True, "error_message": ...}
  so the model can apologise instead of the stream dying.
- Results include both percentage AND raw counts so the model can't
  paraphrase away the denominator.
- No dependency on `agent.py` — can be imported standalone for tests.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("chatbot.metrics")

# Match the path agent.py already uses so prod and tests stay aligned.
CSV_PATH = os.getenv("CHATBOT_CSV_PATH", "/opt/chatbot/data/transactions.csv")

# Amount bucket edges in USD. Matches common payment-analytics brackets.
_AMOUNT_BUCKETS = [
    ("<10", 0, 10),
    ("10-50", 10, 50),
    ("50-200", 50, 200),
    ("200-1000", 200, 1000),
    (">=1000", 1000, float("inf")),
]

_df = None
_df_lock = threading.Lock()


def _load_df():
    """Load the CSV once, lazily, behind a lock. Returns the DataFrame or
    raises — callers of the public functions catch the exception and
    return an error dict.

    Normalises two schema variants: the production SaaS-billing schema
    (column ``timestamp``, ``retry_depth``) and the generator-native
    schema (``created_at``, ``retry_count``). Both map onto the internal
    names used by the metric functions.
    """
    global _df
    if _df is not None:
        return _df
    with _df_lock:
        if _df is not None:
            return _df
        import pandas as pd
        path = Path(CSV_PATH)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found at {CSV_PATH}")
        df = pd.read_csv(path, low_memory=False)

        # Schema normalisation: map generator-native columns to the names
        # BASE_PROMPT (and this module) use. Non-destructive — adds new
        # column only if the target name is missing.
        if "timestamp" not in df.columns and "created_at" in df.columns:
            df["timestamp"] = df["created_at"]
        if "retry_depth" not in df.columns and "retry_count" in df.columns:
            df["retry_depth"] = df["retry_count"]
        if "decline_reason" not in df.columns and "response_code" in df.columns:
            df["decline_reason"] = df["response_code"]

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        _df = df
        log.info("metrics_tool CSV loaded rows=%d cols=%d", len(df), len(df.columns))
        return _df


def _amount_bucket_filter(df, amount_bucket: str | None):
    """Return a slice of df filtered to the named amount bucket.

    Returns df unchanged if bucket is None or unrecognised.
    """
    if not amount_bucket:
        return df
    bucket_map = {name: (lo, hi) for (name, lo, hi) in _AMOUNT_BUCKETS}
    if amount_bucket not in bucket_map:
        return df
    lo, hi = bucket_map[amount_bucket]
    if "amount_usd" not in df.columns:
        return df
    return df[(df["amount_usd"] >= lo) & (df["amount_usd"] < hi)]


def _err(message: str, **extra: Any) -> dict[str, Any]:
    payload = {"error": True, "error_message": message}
    payload.update(extra)
    return payload


# --- Public metric functions -------------------------------------------------


def soft_decline_recovery_rate(
    country: str,
    response_code: str | None = None,
    amount_bucket: str | None = None,
) -> dict[str, Any]:
    """Compute soft-decline retry-recovery rate for a country.

    Returns both attempt-level (approved retries / total retries) and
    subscription-level (subs with any approved attempt after a soft decline
    / subs with a soft decline) rates so the caller can cite the one the
    user actually wanted — and so the model can't paraphrase away the
    definition.

    Parameters
    ----------
    country: ISO-2 country code, e.g. "BR", "IN", "US". Case-insensitive.
    response_code: Optional decline_reason filter (e.g. "do_not_honor",
                   "insufficient_funds"). If None, all soft declines are
                   counted.
    amount_bucket: Optional bucket name: "<10", "10-50", "50-200",
                   "200-1000", ">=1000".
    """
    try:
        df = _load_df()
    except Exception as e:
        return _err(f"could not load CSV: {e}")

    if not country or not isinstance(country, str):
        return _err("country is required (ISO-2, e.g. 'BR')")
    country_code = country.strip().upper()

    required = {"customer_country", "decline_category", "subscription_id",
                "is_approved", "retry_depth"}
    missing = required - set(df.columns)
    if missing:
        return _err(f"CSV missing required columns: {sorted(missing)}")

    scope = df[df["customer_country"].astype(str).str.upper() == country_code]
    scope = _amount_bucket_filter(scope, amount_bucket)
    if len(scope) == 0:
        return _err(f"no rows for country {country_code}"
                    + (f" (amount_bucket={amount_bucket})" if amount_bucket else ""))

    soft = scope[scope["decline_category"].astype(str).str.lower() == "soft"]
    if response_code:
        rc = response_code.strip().lower()
        if "decline_reason" in soft.columns:
            soft = soft[soft["decline_reason"].astype(str).str.lower() == rc]
        else:
            return _err("decline_reason column not available for response_code filter")
    if len(soft) == 0:
        return _err(f"no soft declines for country {country_code}"
                    + (f" reason={response_code}" if response_code else ""))

    # Attempt-level: of all retry attempts belonging to soft-declined subs,
    # what fraction approved? retry_depth >= 1 means it's a retry.
    soft_sub_ids = set(soft["subscription_id"].dropna().unique())
    retries = scope[(scope["retry_depth"] >= 1)
                    & (scope["subscription_id"].isin(soft_sub_ids))]
    retries_total = int(len(retries))
    retries_approved = int(retries["is_approved"].sum()) if retries_total else 0
    attempt_recovery = (retries_approved / retries_total) if retries_total else 0.0

    # Subscription-level: of the subs that saw a soft decline, how many
    # eventually had any approved attempt?
    approved_sub_ids = set(
        scope[scope["is_approved"] == True]["subscription_id"].dropna().unique()
    )
    subs_total = len(soft_sub_ids)
    subs_recovered = len(soft_sub_ids & approved_sub_ids)
    sub_recovery = (subs_recovered / subs_total) if subs_total else 0.0

    # Dollar value at stake on the soft-decline attempts themselves.
    dollar_at_stake = 0.0
    if "amount_usd" in soft.columns:
        dollar_at_stake = float(soft["amount_usd"].sum())

    return {
        "country": country_code,
        "response_code": response_code,
        "amount_bucket": amount_bucket,
        "soft_decline_attempts": int(len(soft)),
        "unique_subscriptions_with_soft_decline": subs_total,
        "subscriptions_recovered": subs_recovered,
        "subscription_level_recovery_rate": round(sub_recovery, 4),
        "retry_attempts_on_those_subs": retries_total,
        "retry_attempts_approved": retries_approved,
        "attempt_level_retry_approval_rate": round(attempt_recovery, 4),
        "dollars_at_stake_on_soft_declines_usd": round(dollar_at_stake, 2),
        "definition_note": (
            "subscription_level_recovery_rate = subs with any approved "
            "attempt / subs that saw a soft decline. "
            "attempt_level_retry_approval_rate = approved retries / total "
            "retry attempts (retry_depth>=1) on those subs. These two "
            "numbers answer different questions — quote the one the user "
            "asked for explicitly."
        ),
        "source": "metrics_tool.soft_decline_recovery_rate (deterministic)",
    }


def retry_recovery_by_category(
    country: str,
    vertical: str | None = None,
) -> dict[str, Any]:
    """Break down attempt-level retry approval rate by decline_category
    (soft / hard / fraud) for a country. Optionally filter by sku_tier
    (Starter / Pro / Enterprise) as a proxy for 'vertical'.

    Returned rates are attempt-level: approved retries / total retries.
    """
    try:
        df = _load_df()
    except Exception as e:
        return _err(f"could not load CSV: {e}")

    if not country or not isinstance(country, str):
        return _err("country is required (ISO-2, e.g. 'BR')")
    country_code = country.strip().upper()

    required = {"customer_country", "decline_category", "retry_depth", "is_approved"}
    missing = required - set(df.columns)
    if missing:
        return _err(f"CSV missing required columns: {sorted(missing)}")

    scope = df[df["customer_country"].astype(str).str.upper() == country_code]
    if vertical and "sku_tier" in scope.columns:
        scope = scope[scope["sku_tier"].astype(str).str.lower() == vertical.lower()]
    if len(scope) == 0:
        return _err(f"no rows for country {country_code}"
                    + (f" tier={vertical}" if vertical else ""))

    retries = scope[scope["retry_depth"] >= 1]
    if len(retries) == 0:
        return _err(f"no retry rows for country {country_code}")

    breakdown: dict[str, dict[str, Any]] = {}
    for cat, sub in retries.groupby(retries["decline_category"].astype(str).str.lower()):
        n = int(len(sub))
        approved = int(sub["is_approved"].sum())
        breakdown[cat] = {
            "retry_attempts": n,
            "approved_retries": approved,
            "attempt_level_retry_approval_rate": round(approved / n, 4) if n else 0.0,
        }

    overall_n = int(len(retries))
    overall_approved = int(retries["is_approved"].sum())

    return {
        "country": country_code,
        "vertical_filter": vertical,
        "by_category": breakdown,
        "overall_retry_attempts": overall_n,
        "overall_approved_retries": overall_approved,
        "overall_attempt_level_retry_approval_rate":
            round(overall_approved / overall_n, 4) if overall_n else 0.0,
        "definition_note": (
            "Rates are attempt-level: approved retries / total retries where "
            "retry_depth>=1. Use soft_decline_recovery_rate for "
            "subscription-level recovery on soft declines specifically."
        ),
        "source": "metrics_tool.retry_recovery_by_category (deterministic)",
    }


def approval_drop_causes(
    country: str,
    timeframe_days: int = 30,
) -> dict[str, Any]:
    """Identify the top drivers of approval-rate change over the last
    ``timeframe_days`` for a country, compared to the prior window of the
    same length. Returns deltas (percentage points) with the number of rows
    in each slice so the model can cite magnitudes honestly.

    The 'last' window is anchored on the dataset's max timestamp, not
    pd.Timestamp.now() — the CSV is historical and 'now' is meaningless.
    """
    try:
        df = _load_df()
    except Exception as e:
        return _err(f"could not load CSV: {e}")

    if not country or not isinstance(country, str):
        return _err("country is required (ISO-2, e.g. 'BR')")
    country_code = country.strip().upper()
    if timeframe_days <= 0 or timeframe_days > 365:
        return _err("timeframe_days must be between 1 and 365")

    required = {"customer_country", "is_approved", "timestamp"}
    missing = required - set(df.columns)
    if missing:
        return _err(f"CSV missing required columns: {sorted(missing)}")

    scope = df[df["customer_country"].astype(str).str.upper() == country_code]
    scope = scope.dropna(subset=["timestamp"])
    if len(scope) == 0:
        return _err(f"no dated rows for country {country_code}")

    import pandas as pd
    max_ts = scope["timestamp"].max()
    recent_start = max_ts - pd.Timedelta(days=timeframe_days - 1)
    prior_start = recent_start - pd.Timedelta(days=timeframe_days)
    recent = scope[(scope["timestamp"] >= recent_start)
                   & (scope["timestamp"] <= max_ts)]
    prior = scope[(scope["timestamp"] >= prior_start)
                  & (scope["timestamp"] < recent_start)]

    if len(recent) == 0 or len(prior) == 0:
        return _err("not enough data to compare windows")

    def _rate(sub):
        return float(sub["is_approved"].mean()) if len(sub) else 0.0

    recent_rate = _rate(recent)
    prior_rate = _rate(prior)
    delta_overall_pp = round((recent_rate - prior_rate) * 100.0, 2)

    # Per-cause breakdown: change in share of declines by decline_reason.
    causes: dict[str, dict[str, Any]] = {}
    if "decline_reason" in scope.columns:
        def _cause_share(sub):
            declined = sub[sub["is_approved"] == False]
            total = len(declined)
            if total == 0:
                return {}
            return (declined["decline_reason"].astype(str).str.lower()
                    .value_counts(normalize=True).round(4).to_dict())

        recent_shares = _cause_share(recent)
        prior_shares = _cause_share(prior)
        all_reasons = set(recent_shares) | set(prior_shares)
        for reason in all_reasons:
            r_share = recent_shares.get(reason, 0.0)
            p_share = prior_shares.get(reason, 0.0)
            delta_pp = round((r_share - p_share) * 100.0, 2)
            causes[reason] = {
                "recent_share_of_declines": round(r_share, 4),
                "prior_share_of_declines": round(p_share, 4),
                "delta_pp": delta_pp,
            }
        # Sort by absolute delta, top 5.
        sorted_causes = dict(sorted(causes.items(),
                                    key=lambda kv: abs(kv[1]["delta_pp"]),
                                    reverse=True)[:5])
    else:
        sorted_causes = {}

    return {
        "country": country_code,
        "timeframe_days": timeframe_days,
        "window_recent": {
            "start": str(recent_start.date()),
            "end": str(max_ts.date()),
            "rows": int(len(recent)),
            "approval_rate": round(recent_rate, 4),
        },
        "window_prior": {
            "start": str(prior_start.date()),
            "end": str((recent_start - pd.Timedelta(days=1)).date()),
            "rows": int(len(prior)),
            "approval_rate": round(prior_rate, 4),
        },
        "delta_approval_rate_pp": delta_overall_pp,
        "top_cause_shifts_by_decline_reason": sorted_causes,
        "source": "metrics_tool.approval_drop_causes (deterministic)",
    }


# --- Tool schema + dispatch --------------------------------------------------

METRICS_TOOL_SCHEMA: dict[str, Any] = {
    "name": "metrics_tool",
    "description": (
        "Deterministic pandas-backed calculator for common multi-hop CSV "
        "metrics: soft-decline retry recovery, retry recovery by category, "
        "and approval-drop cause analysis. Use this FIRST for any question "
        "about retries, recovery, or period-over-period approval shifts "
        "before falling back to `code_execution`. Returns both attempt-level "
        "and subscription-level figures where applicable so the answer "
        "reconciles to a definition, not a free-form estimate."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": [
                    "soft_decline_recovery_rate",
                    "retry_recovery_by_category",
                    "approval_drop_causes",
                ],
                "description": (
                    "Which deterministic metric to compute. "
                    "soft_decline_recovery_rate: attempt- and sub-level "
                    "recovery for soft declines in a country. "
                    "retry_recovery_by_category: attempt-level retry "
                    "approval rate split by decline_category for a country. "
                    "approval_drop_causes: delta approval rate for the last "
                    "N days vs the prior N-day window, with per-cause shifts."
                ),
            },
            "country": {
                "type": "string",
                "description": "ISO-2 country code (e.g. 'BR', 'IN'). Required.",
            },
            "response_code": {
                "type": "string",
                "description": (
                    "Optional decline_reason filter for "
                    "soft_decline_recovery_rate (e.g. 'do_not_honor')."
                ),
            },
            "amount_bucket": {
                "type": "string",
                "enum": ["<10", "10-50", "50-200", "200-1000", ">=1000"],
                "description": (
                    "Optional amount-bucket filter for "
                    "soft_decline_recovery_rate."
                ),
            },
            "vertical": {
                "type": "string",
                "description": (
                    "Optional sku_tier filter ('Starter' | 'Pro' | "
                    "'Enterprise') for retry_recovery_by_category."
                ),
            },
            "timeframe_days": {
                "type": "integer",
                "description": (
                    "Window length in days for approval_drop_causes "
                    "(default 30, max 365)."
                ),
                "default": 30,
            },
        },
        "required": ["metric", "country"],
    },
}


def dispatch_metrics_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Route a metrics_tool invocation to the right function. Never raises."""
    try:
        metric = (args or {}).get("metric", "")
        country = (args or {}).get("country", "")
        if metric == "soft_decline_recovery_rate":
            return soft_decline_recovery_rate(
                country=country,
                response_code=args.get("response_code"),
                amount_bucket=args.get("amount_bucket"),
            )
        if metric == "retry_recovery_by_category":
            return retry_recovery_by_category(
                country=country,
                vertical=args.get("vertical"),
            )
        if metric == "approval_drop_causes":
            return approval_drop_causes(
                country=country,
                timeframe_days=int(args.get("timeframe_days") or 30),
            )
        return _err(f"unknown metric '{metric}' — allowed: "
                    "soft_decline_recovery_rate, retry_recovery_by_category, "
                    "approval_drop_causes")
    except Exception as e:  # noqa: BLE001 — we promise not to raise
        log.exception("metrics_tool dispatch failed")
        return _err(f"internal error computing {args.get('metric')}: {e}")


__all__ = [
    "METRICS_TOOL_SCHEMA",
    "dispatch_metrics_tool",
    "soft_decline_recovery_rate",
    "retry_recovery_by_category",
    "approval_drop_causes",
]
