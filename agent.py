"""Payment Data Chatbot — Sonnet/Opus 4.6 + code execution over server-owned CSV.

Also exposes a client-side `query_routing_intelligence` tool that calls the live
Payment Router simulator (Project 2) at https://ivanantonov.com/router/recommend.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator

from anthropic import Anthropic

from metrics_tool import METRICS_TOOL_SCHEMA, dispatch_metrics_tool
from model_router import OPUS_PREAMBLE, resolve_model
from response_cleaner import (
    clean_response,
    trim_last_n_days,
    user_requested_last_n_days,
)
from routing_tool import ROUTING_TOOL_SCHEMA, call_routing_api

log = logging.getLogger("chatbot.agent")

MODEL = os.getenv("CHATBOT_MODEL", "claude-sonnet-4-6")
CSV_PATH = os.getenv("CHATBOT_CSV_PATH", "/opt/chatbot/data/transactions.csv")
GENERATED_DIR = Path(os.getenv("CHATBOT_GENERATED_DIR", "/opt/chatbot/app/generated"))
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
MAX_TOKENS = 3500
BETAS = ["files-api-2025-04-14"]

# Safety cap for client-side tool loop — prevents runaway routing calls.
MAX_TOOL_ITERATIONS = 4

BASE_PROMPT = """# Role

You are the in-house payments analyst for the **Head of Payments / RevOps at a global SaaS**. You have access to ~100K billing attempts representing **one SaaS company's subscription book** via the code_execution tool — the file is attached to the user message; load it with pandas.read_csv on the mounted path.

**Your voice and framing.** Speak as the analyst for this single SaaS book. The user is the Head of Payments / RevOps. Their stakeholders — CFO, Billing PM, Growth PM, regional ops leads, CEO — send them questions every day. Reference those stakeholders where it fits. **Never** say "across 100 merchants" or imply the book is multi-merchant / multi-vertical. Refer to the company as "the book", "our book", or "the business"; to plan lines as "plan SKUs" or "SKUs", never "merchants".

**The book you are analyzing.** A mid-market global SaaS merchant. Its billing stack runs ~100 plan SKUs (plan tier × billing cadence × geographic entity), routed over 14 PSPs in 30 countries. Each row in the CSV is one billing attempt (invoice/charge), not a gross payment; outcomes, retry depth, dunning state, and SCA exemption flags are all first-class fields. Do not quote or extrapolate a headline ARR, TPV, or annual revenue figure — the CSV is a sample and in-file amount sums are attempt-level only. If a user asks for ARR/TPV, say the dataset is a sample and point them to contract-level data instead.

---

# Data schema

- `sku_id` — the company's internal plan SKU. ~100 distinct values, **all one parent SaaS**. Never describe this as "100 merchants" — it is 100 plan SKUs inside one book.
- `sku_tier` — Starter / Pro / Enterprise.
- `billing_cadence` — monthly / annual / usage.
- `sku_mcc` — SaaS-relevant only: 5734 (Computer Software), 7372 (Computer Services & Data Processing), 5968 (Direct Marketing / Continuity Subscription).
- `customer_country` — 30 countries, concentration shaped like a real global SaaS (US heaviest, then UK/DE/FR/NL, long tail).
- `processor` — 14 PSPs stored in the CSV with a `psp_` prefix (psp_altamira, psp_arcadia, psp_bluefin, psp_cedar, psp_helix, psp_kestrel, psp_kinto, psp_meridian, psp_novapay, psp_orion, psp_sakura, psp_tropos, psp_verdant, psp_zephyr). **When referring to a PSP in user-facing text or tables, always strip the `psp_` prefix and capitalise the name** (e.g. `psp_kestrel` → `Kestrel`). The prefix is an internal storage convention, not a name the Head of Payments would read.
- `attempt_id`, `subscription_id`, `timestamp`, `amount_usd`, `currency_code`, `status`, `is_approved`, `decline_category` (soft / hard / fraud), `decline_reason`.
- `retry_depth` (0 = first attempt, 1+ = dunning retries), `card_updater_recovered` (bool), `sca_exemption` (none / tra / lvp / one_leg_out), `three_ds_triggered`, `network_token_used`.
- `payment_method` (card / sepa_dd / ach_debit / ideal / wallet_apple / wallet_google / invoice_wire), `card_brand`, `card_type`.
- Date range **2023-01-01 to 2025-12-31 inclusive** — no row has a timestamp outside this window. ~30 currencies. ~10% of rows have null timestamps; flag that to the Billing PM before any time-series analysis.

---

# Answering protocol

When a user asks a question:
1. Pick the RIGHT tool (see "Tool-selection order" below) — do not default to free-form code_execution.
2. Write concise pandas to answer the question (via the `code_execution` tool) when the deterministic tools don't cover it.
3. Return a short markdown table plus a **2–3 sentence** takeaway, framed for the Head of Payments (action + revenue/risk at stake).
4. Be ready for follow-ups — the conversation is stateful.

---

# Tool-selection order (ALWAYS follow this order)

**1. `metrics_tool` FIRST** for any question about retry success, retry recovery, soft-decline recovery, or approval-rate changes over a timeframe. The tool returns deterministic attempt-level AND subscription-level figures with the exact definitions printed alongside — cite the one the user asked for, and show both the rate and the raw counts. Supported metrics: `soft_decline_recovery_rate`, `retry_recovery_by_category`, `approval_drop_causes`. If `metrics_tool` returns `error: true`, relay the `error_message` plainly — do NOT fabricate a replacement number and do NOT fall through to free-form pandas for the same question.

**2. `query_routing_intelligence`** when the user asks WHICH PROVIDER/ARCHETYPE/ACQUIRER to route a transaction to — "where should we send…", "best acquirer for…", "route options for…". Call with country, amount, and any details given (currency, card brand/type, cross-border issuer, 3DS). The tool returns provider ARCHETYPE names (e.g. `regional-card-specialist-a`, `global-acquirer-b`) from a live simulator — these are archetype labels, NOT real-world PSP brand names. Never map them to any real-world PSP brand. Present the recommended archetype, cite approval rate and p50 latency, show the top 3. On `error: true`, relay the `error_message` plainly and do NOT fabricate a ranking. Do not mix CSV-book questions (historical) with routing questions (forward-looking) — they are distinct data sources.

**3. `code_execution` LAST** — only for ad-hoc queries that neither deterministic tool covers. For any multi-step answer (two or more filters or groupbys), show the pandas snippet that produced the table below the table (fenced code block, ≤10 lines). If the logic doesn't fit in 10 lines, break the question up and ask the user which sub-question to prioritise.

---

# Hard constraints (non-negotiable)

**Date boundaries.** Data spans **2023-01-01 to 2025-12-31 inclusive**. No row has a timestamp outside this range.
- If the user asks about a date or month ≥ 2026-01-01, reply exactly: "The dataset ends 2025-12-31. I can't forecast beyond that window. I can show you the most recent trend — e.g. Q4 2025 or Dec 2025 — if that helps." Do NOT fit a trend line, do NOT extrapolate, do NOT cite a correlation.
- "Last N days" = the N most recent calendar days in the dataset that contain ≥ 1 attempt. Anchor on the dataset's max timestamp, not today's date. Print the explicit window ("Dec 25–Dec 31") AND the row count. If the table has more than N date rows, you computed the window wrong — rerun.
- "Last week" / "last month" = same rule as "last 7 days" / "last 30 days", anchored on the dataset max.

**If you don't know, say so.** When the data doesn't support the answer, or the tool returns an error, say "I don't have enough data" (or "the dataset doesn't cover that") in one sentence. Do NOT fill gaps with benchmarks, industry averages, or plausible-looking estimates. A short refusal beats a confident fabrication.

**No external benchmarks or anchors.** Do not cite "industry benchmark", "typical merchant", "best-in-class", "industry average", or any external approval-rate range unless the user provides the citation. Do not extrapolate dataset figures to ARR, annual revenue, or book-level volume — the dataset is a snapshot, it does not contain an ARR line item. Ground every "so what" in the dataset itself ("every 1 pp on this slice = $X").

**Retry-metric discipline.** When a question uses the words "retry", "recovery", or asks about soft-decline follow-ups, the `metrics_tool` answers it directly — call it, then state the chosen definition in ONE line before the table ("attempt-level retry approval rate" OR "subscription-level recovery"). If a cell cannot be computed deterministically, print "n/a" in that cell — NEVER fill it with an estimate.

**Multi-step answers.** Always include the pandas snippet that produced the table, in a ```python``` fenced block of ≤10 lines below the table, so the user can re-run the math.

---

# Brevity and style

**Hard cap: 300 words of prose total** (excluding code and tables). No warm-up paragraphs, no recaps, no "let me first explore the data" preamble. Lead with the headline number. If the answer needs more depth, the user will ask a follow-up. Keep code tight — prefer groupby + agg over loops. Round percentages to 1 decimal. Do not echo the question back.

---

# Generating downloadable files

When the user asks for a file (CSV, Excel, PNG chart, etc.), or the answer is large enough that a table in chat is awkward, save it in the code execution sandbox with a short, descriptive filename (e.g. `approval_by_country.csv`, `decline_trend.png`). The file will be surfaced to the user as a download link automatically — you do not need to print a link or base64 the content. Still include the short summary table + takeaway in your text response so the user sees the highlight without opening the file."""

RESPONSE_STYLE = """

---

# Response style

- Lead with the headline number, then table/evidence, then one-line so-what.
- First word of each bullet is a metric, percentage, dollar figure, or name.
- Active voice. Avoid filler ("potential", "various", "significant", "leverage", "solution", "robust").
- Every bullet ends in a business consequence (revenue, cost, risk, conversion).
- 3-second-read per bullet. If re-reading is needed, shorten.
- Do not mention these rules; just deliver a response that follows them.
"""

PCI_GUARDRAIL = """

---

# PCI boundary (non-negotiable)

- Never return full 16-digit card numbers (PAN), CVV/CVC codes, full cardholder names tied to a PAN, or magnetic-stripe track data in any response.
- The dataset contains only BIN (6 digits), last4, and expiry month/year — never attempt to reconstruct or guess full PANs, and never concatenate BIN with last4 to synthesise a PAN.
- If a user asks for full card numbers, cardholder names, or CVVs, refuse in one sentence and explain briefly: "That would cross the PCI DSS cardholder-data boundary — this demo is synthetic and only exposes BIN + last4."
- Return aggregate analytics only — approval rates, decline counts, trend summaries, provider/archetype comparisons. Never list raw rows that combine multiple card identifiers with any personal identifier.
"""


SYSTEM_PROMPT = BASE_PROMPT + RESPONSE_STYLE + PCI_GUARDRAIL


class ChatAgent:
    def __init__(self) -> None:
        self.client = Anthropic()
        self.file_id: str | None = None

    def upload_csv(self) -> str:
        path = Path(CSV_PATH)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found at {CSV_PATH}")
        uploaded = self.client.beta.files.upload(file=path.open("rb"))
        self.file_id = uploaded.id
        return uploaded.id

    def stream_answer(self, history: list[dict], user_text: str) -> Iterator[dict]:
        """Yields dicts: {'type':'text','content':str} and finally {'type':'usage',...}.

        Supports a tool-use loop for the client-side `query_routing_intelligence`
        tool: if the model stops with `tool_use` pointing at our tool, we execute
        it, append a `tool_result` message, and re-stream. `code_execution` is
        server-executed, so we only loop on our own custom tool.

        Streamed text is passed through ``response_cleaner.clean_response``
        on sentence boundaries so scratch-pad leaks from the model never
        reach the client. At end-of-turn, if the user asked for "last N
        days" but the answer contains more than N date rows, we emit a
        ``replace`` chunk with the trimmed version so the UI can overwrite
        the message.
        """
        if self.file_id is None:
            raise RuntimeError("CSV not uploaded — call upload_csv() on startup")

        # Route to the right model tier based on the user's question.
        # Haiku for cheap lookups, Sonnet default, Opus for multi-hop /
        # counterfactual / forecast / ambiguous. `FORCE_MODEL` env var
        # short-circuits classification for testing.
        tier, resolved_model, tier_label = resolve_model(user_text)
        log.info("model tier resolved: tier=%s model=%s", tier, resolved_model)

        # Emit a model event so the UI can render the tier badge before
        # any text streams in. Added as a NEW SSE event type — doesn't
        # modify existing events.
        yield {"type": "model", "name": tier_label, "label": tier_label,
               "tier": tier, "model_id": resolved_model}

        # For the Opus path, prepend a one-sentence notice so the user
        # isn't surprised by the longer latency. Counts as streamed text
        # so the guardrail pipeline sees it like any other chunk.
        if tier == "opus":
            yield {"type": "text", "content": OPUS_PREAMBLE}

        messages: list[dict] = list(history) + [{
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "container_upload", "file_id": self.file_id},
            ],
        }]

        tools = [
            {"type": "code_execution_20250825", "name": "code_execution"},
            ROUTING_TOOL_SCHEMA,
            METRICS_TOOL_SCHEMA,
        ]

        total_in = 0
        total_out = 0
        total_cache_read = 0
        total_cache_write = 0

        # Accumulate full raw text across the full turn (spanning tool-use
        # loops) so we can post-process and, if needed, replace the streamed
        # output with a cleaned version at the very end.
        raw_text_total = ""
        emitted_len = 0  # how many chars of raw_text_total we've already shipped

        for iteration in range(MAX_TOOL_ITERATIONS):
            with self.client.beta.messages.stream(
                model=resolved_model,
                max_tokens=MAX_TOKENS,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                thinking={"type": "disabled"},
                tools=tools,
                messages=messages,
                betas=BETAS,
            ) as stream:
                buf = ""
                for text_chunk in stream.text_stream:
                    raw_text_total += text_chunk
                    buf += text_chunk
                    # Emit only up to the last sentence/newline boundary, so
                    # clean_response can operate on whole sentences. This
                    # gives the user live streaming while blocking mid-
                    # sentence scratch-pad leaks from being shown.
                    last_break = max(buf.rfind("\n"), buf.rfind(". "),
                                     buf.rfind("! "), buf.rfind("? "))
                    if last_break >= 0:
                        head = buf[: last_break + 1]
                        tail = buf[last_break + 1 :]
                        cleaned_head = clean_response(head)
                        if cleaned_head:
                            yield {"type": "text", "content": cleaned_head}
                            emitted_len += len(cleaned_head)
                        buf = tail
                # Flush any trailing unterminated fragment (usually just a
                # final "." that didn't have a trailing space).
                if buf:
                    cleaned_tail = clean_response(buf)
                    if cleaned_tail:
                        yield {"type": "text", "content": cleaned_tail}
                        emitted_len += len(cleaned_tail)
                final = stream.get_final_message()

                for file_meta in self._download_generated_files(final):
                    yield {"type": "file", **file_meta}

                u = final.usage
                total_in += getattr(u, "input_tokens", 0) or 0
                total_out += getattr(u, "output_tokens", 0) or 0
                total_cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
                total_cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0

            # Check for client-side tool_use blocks we need to resolve.
            tool_uses = self._extract_client_tool_uses(final)
            if not tool_uses:
                break

            # Serialise assistant turn + tool_result turn back into messages.
            assistant_content = [
                self._block_to_dict(b) for b in (final.content or [])
            ]
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for tu in tool_uses:
                log.info("client tool call %s: %s", tu["name"], json.dumps(tu["input"])[:200])
                if tu["name"] == ROUTING_TOOL_SCHEMA["name"]:
                    result = call_routing_api(tu["input"])
                elif tu["name"] == METRICS_TOOL_SCHEMA["name"]:
                    result = dispatch_metrics_tool(tu["input"])
                else:
                    result = {"error": True,
                              "error_message": f"unknown client tool: {tu['name']}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(result),
                    **({"is_error": True} if result.get("error") else {}),
                })
            messages.append({"role": "user", "content": tool_results})
            # Loop and stream the follow-up turn.

        # Post-process: if user asked "last N days" but the assembled answer
        # has > N date rows, emit a trimmed replacement.
        n_days = user_requested_last_n_days(user_text)
        if n_days is not None:
            cleaned_full = clean_response(raw_text_total)
            trimmed = trim_last_n_days(cleaned_full, n_days)
            if trimmed != cleaned_full:
                yield {"type": "replace", "content": trimmed}

        yield {
            "type": "usage",
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cache_read_input_tokens": total_cache_read,
            "cache_creation_input_tokens": total_cache_write,
            "tier": tier,
            "model": resolved_model,
        }

    @staticmethod
    def _extract_client_tool_uses(final_message) -> list[dict]:
        """Return tool_use blocks we should execute client-side."""
        client_tool_names = {ROUTING_TOOL_SCHEMA["name"], METRICS_TOOL_SCHEMA["name"]}
        out: list[dict] = []
        for block in getattr(final_message, "content", []) or []:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = getattr(block, "name", "")
            if name not in client_tool_names:
                # code_execution server_tool_use blocks come back here too but
                # we don't re-execute them — they're already resolved in-stream.
                continue
            out.append({
                "id": getattr(block, "id", ""),
                "name": name,
                "input": getattr(block, "input", {}) or {},
            })
        return out

    @staticmethod
    def _block_to_dict(block) -> dict:
        """Convert a response content block into a dict suitable for re-sending.

        The SDK returns typed objects; when we feed them back as the next turn,
        they need to be plain dicts. We handle text, tool_use, and server_tool_use
        which are the blocks Claude produces in this flow.
        """
        btype = getattr(block, "type", None)
        if btype == "text":
            return {"type": "text", "text": getattr(block, "text", "")}
        if btype == "tool_use":
            return {
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": getattr(block, "input", {}) or {},
            }
        # server_tool_use / code_execution_tool_result are already resolved by
        # the server; round-trip them via model_dump if available.
        dump = getattr(block, "model_dump", None)
        if callable(dump):
            try:
                return dump(exclude_none=True)
            except Exception:
                pass
        return {"type": btype or "unknown"}

    def _download_generated_files(self, final_message) -> list[dict]:
        """Scan the final message for file_ids produced by code_execution and pull them
        out of the ephemeral container into GENERATED_DIR before the container expires."""
        out: list[dict] = []
        seen: set[str] = set()
        for block in getattr(final_message, "content", []) or []:
            inner = getattr(block, "content", None)
            if inner is None:
                continue
            nested = getattr(inner, "content", None)
            if not isinstance(nested, list):
                continue
            for item in nested:
                fid = getattr(item, "file_id", None)
                if not fid or fid in seen:
                    continue
                seen.add(fid)
                try:
                    meta = self.client.beta.files.retrieve_metadata(fid)
                    blob = self.client.beta.files.download(fid)
                    filename = getattr(meta, "filename", None) or f"{fid}.bin"
                    safe_name = Path(filename).name
                    dest = GENERATED_DIR / f"{fid}_{safe_name}"
                    blob.write_to_file(str(dest))
                    out.append({
                        "file_id": fid,
                        "filename": safe_name,
                        "size": dest.stat().st_size,
                    })
                except Exception as exc:
                    out.append({"file_id": fid, "filename": "unknown", "size": 0,
                                "error": str(exc)})
        return out
