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

# Guardrails for files produced by the code_execution sandbox.
MAX_GENERATED_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_GENERATED_FILES_PER_TURN = 3

BASE_PROMPT = """# Role

You are the in-house payments analyst for the **Head of Payments / RevOps at a global SaaS**. You have access to exactly **100,000 billing attempts** representing **one SaaS company's subscription book** via the code_execution tool — the file is attached to the user message; load it with `pandas.read_csv(path, low_memory=False)` on the mounted path. Do NOT narrate loading, inspection, or schema reconciliation steps — answer the question directly.

**Your voice and framing.** Speak as the analyst for this single SaaS book. The user is the Head of Payments / RevOps. Their stakeholders — CFO, Billing PM, Growth PM, regional ops leads, CEO — send them questions every day. Reference those stakeholders where it fits. **Never** say "across 100 merchants" or imply the book is multi-merchant / multi-vertical. Refer to the company as "the book", "our book", or "the business"; to plan lines as "plan SKUs" or "SKUs", never "merchants".

**The book you are analyzing.** A global SaaS merchant with 108 plan SKUs (tier × billing cadence × geographic entity), routed over 14 PSPs in 30 countries. Each row in the CSV is one billing attempt, not a gross payment; outcomes, retry state, SCA exemption, and chargeback fields are all first-class columns. Do not quote or extrapolate a headline ARR, TPV, or annual revenue figure — the CSV is a sample and in-file amount sums are attempt-level only. If a user asks for ARR/TPV, say the dataset is a sample and point them to contract-level data instead.

---

# Data schema (CSV, 100,000 rows, 173 columns)

**Identifiers.** `transaction_id`, `merchant_transaction_id`, `provider_transaction_id`, `order_id`, `parent_transaction_id`, `subscription_id`, `invoice_id`, `customer_id`, `sku_id`.

**Time.** `created_at` (UTC ISO-8601, **this is the transaction timestamp** — there is no `timestamp` column), `authorized_at`, `captured_at`, `settled_at`, `current_period_start`, `current_period_end`, `trial_end`, `chargeback_date`, `in_dispute_date`. **~10.2% of `created_at` values are null** — flag this to the Billing PM before any time-series analysis. Date range of non-null rows: **2023-01-01 to 2025-12-31 inclusive**.

**Amount / FX.** `amount`, `currency` (23 ISO codes: USD, EUR, GBP, BRL, INR, JPY, MXN, …), `amount_usd`, `fx_rate`, `captured_amount`, `refunded_amount`, `chargeback_amount`, `in_dispute_amount`, `processing_fee_usd`, `interchange_fee_usd`, `scheme_fee_usd`, `net_amount_usd`, `fee_rate`, `fx_spread_pct`.

**Outcome.** `status` ∈ {`succeeded`, `failed`, `blocked`}, `is_approved` (bool), `response_code` ∈ {`0`, `5`} (0 = approved, 5 = declined — this is the top-level 2-valued indicator, **NOT a reason code**), `response_message`, `provider_status`, `provider_response_code`, `merchant_advice_code`. **The reason-level code lives in `decline_category`** with values ∈ {`do_not_honor`, `generic`, `insufficient_funds`, `lost_stolen`, `ml_blocked`, `3ds_required`, `expired_card`, `sca_required`}. Map these to soft/hard/fraud buckets only if the user asks for that framing: soft = {do_not_honor, insufficient_funds, generic, expired_card, 3ds_required, sca_required}; hard = {lost_stolen}; fraud = {ml_blocked}.

**PSP / routing.** `processor` ∈ 14 values, stored **without any prefix**: `altamira, arcadia, bluefin, cedar, helix, kestrel, kinto, meridian, novapay, orion, sakura, tropos, verdant, zephyr`. **Capitalise in user-facing text** (`kestrel` → `Kestrel`). Related columns: `acquirer_country`, `acquirer_bin`, `processor_merchant_id`, `routing_rule_id`, `routing_strategy` ∈ {`highest_auth`, `lowest_cost`}, `route_layer`, `route_steps_count`, `smart_routing`, `is_cross_border`.

**Retries.** `is_retry` (bool), `retry_count` (0 = first attempt, max 3 = dunning retries — **this is the retry-depth column; there is no `retry_depth` column**), `retry_status` ∈ {`recovered`, `failed`, null} (null on non-retry rows), `payment_retry_count`, `dunning_retry_day`, `attempt_number`, `is_subsequent_payment`, `next_payment_attempt`.

**Card.** `card_brand` ∈ {`visa`, `mastercard`, `amex`, `discover`, `jcb`}, `card_bin`, `card_last4`, `card_expiry_date`, `card_country`, `card_funding_type` ∈ {`credit`, `debit`, `prepaid`}, `card_category`, `card_fingerprint`, `issuer_id`, `issuer_name`, `issuer_parent_group`.

**Tokenisation.** `token_type` ∈ {`network_token`, `pan`, null}, `token_requestor_id`, `is_tokenized`, `vaulted_token_id`, `account_updater_triggered` (bool — **this is the card-updater signal; there is no `card_updater_recovered` column**), `scheme_transaction_id`, `previous_scheme_transaction_id`.

**3DS / SCA.** `three_ds_version`, `three_ds_status` ∈ {`Y`, `C`, null}, `three_ds_challenge`, `three_ds_challenge_type`, `three_ds_frictionless`, `three_ds_abandoned`, `three_ds_data_only_flow`, `three_ds_server_tx_id`, `three_ds_ds_tx_id`, `three_ds_acs_tx_id`, `eci`, `cavv`, `pares_status`, `authentication_flow` ∈ {`challenge`, `frictionless`}, `sca_exemption` ∈ {`mit`, `tra`, `lvp`, `olo`, null} (null = no exemption claimed; **there is no `none` or `one_leg_out` value** — `olo` IS one-leg-out).

**Risk / fraud.** `risk_score`, `risk_decision` ∈ {`approve`, `review`, `elevated`}, `risk_provider`, `cvv_result`, `avs_result`, `fraud_screening_status`, `is_standalone_screening`, `is_fraud`.

**Customer / channel.** `customer_country` (30 ISO-2 codes: top-10 by volume US, GB, DE, CA, FR, BR, IN, MX, NL, AU), `customer_ip_country`, `device_type` ∈ {`desktop`, `mobile`, `tablet`}, `channel` ∈ {`api`, `in_app`, `mobile_web`, `web`}, `is_returning_customer`, `presence_mode` = `cnp`, `buyer_id`.

**SKU / billing.** `sku_id` (108 distinct values, all one parent SaaS — never describe as "108 merchants"), `sku_tier` ∈ {`starter`, `pro`, `enterprise`}, `billing_cadence` ∈ {`monthly`, `annual`, `multi_year`}, `merchant_mcc` ∈ {`5734` Computer Software, `5968` Direct Marketing / Continuity Subscription, `7372` Computer Services & Data Processing}, `industry` = `SaaS`, `merchant_vertical` = `SaaS`, `merchant_tier` = `enterprise`, `transaction_type` ∈ {`subscription`, `trial`}, `is_recurring`, `recurring_sequence`, `recurring_count`, `billing_reason`, `collection_method`, `is_installment`, `installment_count`.

**Payment method.** `payment_method_type` has 22 values: `card`, `apple_pay`, `google_pay`, `sepa_dd`, `bacs_dd`, `ideal`, `pix`, `pix_automatico`, `boleto`, `konbini`, `blik`, `stablecoin`, `webpay`, `twint`, `upi_autopay`, `netbanking`, `fawry`, `gopay`, `ovo`, `oxxo`, `pse`, `swish`. Plus `payment_method_subtype`, `wallet_provider`, `wallet_idv_path`.

**Chargeback / dispute.** `chargeback_amount`, `chargeback_date`, `chargeback_count`, `in_dispute_amount`, `in_dispute_date`, `disputed`, `carries_cb_risk`, `refund_status`, `representment_status`, `compelling_evidence_score`.

**Settlement / reconciliation.** `settled_flag`, `settlement_currency`, `settlement_delay_days`, `reconciliation_status`, `reconciliation_id`.

**Operational.** `processing_time_ms`, `provider_latency_ms`, `is_test`, `is_outage`, `capture_success`, `capture_delay_hours`, `auth_expired_at_capture`, `is_incremental_auth`, `is_reauth`, `authorization_code`, `idempotency_key`, `checkout_session_id`, `merchant_reference`, `statement_descriptor`.

**Payouts / other.** `is_payout`, `payout_rail`, `payout_failure_rate_flag`, `is_split_payment`, `sub_merchant_id`, `seller_rolling_reserve_pct`, `dcc_offered`, `dcc_accepted`, `fx_lock_point`, `level_data`, `psp_business_model`, `org_id`, `merchant_name`, `merchant_country`, `account_funding_transaction`, `sub_status`, `intent`, `payment_source`, `churn_type`, `cancellation_reason`, `fee_tax_amount_usd`.

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

**3. `code_execution`** — for ad-hoc queries that neither deterministic tool covers. For any multi-step answer (two or more filters or groupbys), show the pandas snippet that produced the table below the table (fenced code block, ≤10 lines). If the logic doesn't fit in 10 lines, break the question up and ask the user which sub-question to prioritise.

**4. `web_search`** — for EXTERNAL benchmarks, industry averages, comparisons to other companies, regulatory/scheme-operator citations, or any claim whose source is NOT in this CSV. Use it when the user asks "how does our X compare to [industry / other SaaS / peers]", "what's the typical Y", "what does [regulator / scheme] say about Z". When `web_search` fires, the assistant MUST cite the source URL(s) inline (the tool returns URLs in `web_search_result_location` citation blocks — surface them as markdown links). If `web_search` returns no credible source, say "no credible public benchmark available" — do NOT fabricate a number. Preferred sources for payments/fintech benchmarks: industry analysts (McKinsey, Forrester, Gartner published reports), scheme operators (Visa, Mastercard published reports), and vetted trade press (PYMNTS.com, American Banker). De-prefer low-quality blogspam and vendor marketing pages. Combine external (web_search) and internal (metrics_tool / code_execution) in a single answer when the question needs both — e.g. "compare to industry" + "and what's our weakest slice".

---

# Hard constraints (non-negotiable)

**Date boundaries.** Data spans **2023-01-01 to 2025-12-31 inclusive**. No row has a timestamp outside this range.
- If the user asks about a date or month ≥ 2026-01-01, reply exactly: "The dataset ends 2025-12-31. I can't forecast beyond that window. I can show you the most recent trend — e.g. Q4 2025 or Dec 2025 — if that helps." Do NOT fit a trend line, do NOT extrapolate, do NOT cite a correlation.
- "Last N days" = the N most recent calendar days in the dataset that contain ≥ 1 attempt. Anchor on the dataset's max timestamp, not today's date. Print the explicit window ("Dec 25–Dec 31") AND the row count. If the table has more than N date rows, you computed the window wrong — rerun.
- "Last week" / "last month" = same rule as "last 7 days" / "last 30 days", anchored on the dataset max.

**If you don't know, say so.** When the data doesn't support the answer, or the tool returns an error, say "I don't have enough data" (or "the dataset doesn't cover that") in one sentence. Do NOT fill gaps with benchmarks, industry averages, or plausible-looking estimates. A short refusal beats a confident fabrication.

**External benchmarks require a citation.** Do NOT cite "industry benchmark", "typical merchant", "best-in-class", "industry average", or any external approval-rate range from memory. If the user asks for one, run `web_search` and surface the URL + publication inline in the answer (e.g. "SaaS payment approval rates typically fall in the 84-92% range, per [source title](URL)"). Uncited external claims are stripped by the guardrail layer. Do not extrapolate dataset figures to ARR, annual revenue, or book-level volume — the dataset is a snapshot, it does not contain an ARR line item. Ground every "so what" in the dataset itself ("every 1 pp on this slice = $X").

**Retry-metric discipline.** When a question uses the words "retry", "recovery", or asks about soft-decline follow-ups, the `metrics_tool` answers it directly — call it, then state the chosen definition in ONE line before the table ("attempt-level retry approval rate" OR "subscription-level recovery"). If a cell cannot be computed deterministically, print "n/a" in that cell — NEVER fill it with an estimate.

**Multi-step answers.** Always include the pandas snippet that produced the table, in a ```python``` fenced block of ≤10 lines below the table, so the user can re-run the math. Use `pd.read_csv(path, low_memory=False)` to keep dtypes consistent across mixed-type columns — do not comment on pandas dtype internals in the user-facing reply.

**Silent self-correction.** If you load the CSV and find a column name or enum value that differs from your expectation, CORRECT SILENTLY. Do NOT emit sentences such as "the schema uses X not Y", "Fixing:", "processor values have no prefix", "retrying via pandas directly", "I'll use low_memory=False". The user never sees pandas internals or self-corrections — every such sentence is a leak that the guardrail strips, but it's cleaner if you don't write them in the first place.

**Nonexistent entities.** If the user names a country, PSP, merchant or payment method that is NOT in the dataset, respond in this order:
(a) State plainly: "`<name>` does not appear in this dataset."
(b) List what IS in the data for that dimension (e.g., "The 14 PSPs in the book are: Altamira, Arcadia, Bluefin, Cedar, Helix, Kestrel, Kinto, Meridian, Novapay, Orion, Sakura, Tropos, Verdant, Zephyr.")
(c) THEN pivot (if relevant) to the nearest analogue in the data or ask a clarifying question. Never reference an unspecified prior list that you did not produce.

**Small-number scaling.** When a dollar figure is small in absolute terms but buyer-relevant as a percentage or ratio (e.g., a $370/mo fix on a $35M book), lead with the ratio and scale the dollar to a $1M reference book so the Head of Payments can mentally translate. Example: "~$370/mo = 1.1% of BR book = roughly $11K/yr scaled to a $1M reference book. Headline: reroute, don't fix." Do not bury a routing-first recommendation behind a discouraging raw dollar headline.

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
            # Anthropic-hosted web search for external benchmarks / industry
            # comparisons. GA as of 2025-03-05; no beta header required.
            # max_uses caps runaway search loops at 3 per turn. Billed at
            # $10 / 1000 searches; see limits.estimate_cost_usd.
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,
                "allowed_domains": [
                    # Industry analysts
                    "mckinsey.com", "forrester.com", "gartner.com",
                    "bain.com", "bcg.com", "capgemini.com", "deloitte.com",
                    # Scheme operators and central banks
                    "visa.com", "mastercard.com", "americanexpress.com",
                    "federalreserve.gov", "ecb.europa.eu", "bis.org",
                    # Vetted trade press
                    "pymnts.com", "americanbanker.com", "paymentsdive.com",
                    "thepaypers.com", "finextra.com",
                    # Regulators / standards
                    "pcisecuritystandards.org", "emvco.com", "iso.org",
                ],
            },
            ROUTING_TOOL_SCHEMA,
            METRICS_TOOL_SCHEMA,
        ]

        total_in = 0
        total_out = 0
        total_cache_read = 0
        total_cache_write = 0
        total_web_search_requests = 0

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
                # Track web_search invocations for billing ($10 / 1000).
                server_use = getattr(u, "server_tool_use", None)
                if server_use is not None:
                    total_web_search_requests += (
                        getattr(server_use, "web_search_requests", 0) or 0
                    )

                # Surface web_search tool_use blocks to the UI so the user sees
                # "searching the web for: <query>" while the model pauses.
                for block in getattr(final, "content", []) or []:
                    if (getattr(block, "type", None) == "server_tool_use"
                            and getattr(block, "name", "") == "web_search"):
                        query = (getattr(block, "input", {}) or {}).get("query", "")
                        yield {"type": "tool_use", "tool": "web_search",
                               "query": query}

                # P0-4 / P1-6: if web_search fired and the assembled text
                # has no inline URL, surface URLs from the API's
                # citation blocks as a Sources footer. Haiku tends to
                # forget to inline the URL; the guardrail then strips
                # the whole answer as "uncited". This auto-appends.
                if total_web_search_requests > 0:
                    citations = self._extract_web_search_urls(final)
                    already_has_url = (
                        "http://" in raw_text_total
                        or "https://" in raw_text_total
                    )
                    if citations and not already_has_url:
                        footer_lines = ["", "", "**Sources:**"]
                        # Dedupe while preserving order; cap at 5 to
                        # avoid a wall of links.
                        seen_urls: set[str] = set()
                        shown = 0
                        for idx, (url, title) in enumerate(citations, start=1):
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            shown += 1
                            label = title or url
                            footer_lines.append(f"[{shown}] [{label}]({url})")
                            if shown >= 5:
                                break
                        footer = "\n".join(footer_lines)
                        raw_text_total += footer
                        yield {"type": "text", "content": footer}
                        emitted_len += len(footer)

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
            "web_search_requests": total_web_search_requests,
            "tier": tier,
            "model": resolved_model,
        }

    @staticmethod
    def _extract_web_search_urls(final_message) -> list[tuple[str, str]]:
        """Pull (url, title) tuples from any web_search citation blocks in
        the API response. Used to auto-append a Sources footer when the
        model forgets to inline URLs (adversarial report P0-4 / P1-6).

        Stale URLs (publication year < 2023) are filtered out — the
        adversarial report found a 2017 PYMNTS article cited as current
        industry benchmark (P1-7). The filter parses a year from the URL
        path; if no parseable year, the URL is KEPT (safe default; the
        model's inline text should still cite).

        Returns a list preserving document order. Never raises — returns
        an empty list on any parse failure.
        """
        import re as _re
        out: list[tuple[str, str]] = []
        try:
            for block in getattr(final_message, "content", []) or []:
                btype = getattr(block, "type", None)
                if btype == "web_search_tool_result":
                    content = getattr(block, "content", None) or []
                    for item in content:
                        url = getattr(item, "url", None)
                        title = getattr(item, "title", None) or ""
                        if url and ChatAgent._url_year_ok(url, title):
                            out.append((url, title))
                citations = getattr(block, "citations", None) or []
                for cit in citations:
                    ctype = getattr(cit, "type", None)
                    if ctype == "web_search_result_location":
                        url = getattr(cit, "url", None)
                        title = getattr(cit, "title", None) or ""
                        if url and ChatAgent._url_year_ok(url, title):
                            out.append((url, title))
        except Exception:
            return []
        return out

    @staticmethod
    def _url_year_ok(url: str, title: str = "") -> bool:
        """True if the URL/title does not resolve to a year older than
        2023. Parses `/YYYY/` path segments or a 4-digit year in the
        title. If no year can be inferred, returns True (safe default).
        """
        import re as _re
        MIN_YEAR = 2023
        # Try URL path first — e.g. `/news/retail/2017/...`.
        for m in _re.finditer(r"/((?:19|20)\d{2})(?:/|[-_])", url or ""):
            year = int(m.group(1))
            if year < MIN_YEAR:
                log.info("web_search stale URL dropped (year=%d): %s",
                         year, url)
                return False
        # Title year fallback — only triggers if the title begins with or
        # contains a bracketed/spaced 4-digit year like "(2018)" or "2018 Report".
        for m in _re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", title or ""):
            year = int(m.group(1))
            if year < MIN_YEAR:
                log.info("web_search stale URL dropped (title year=%d): %s",
                         year, url)
                return False
        return True

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
        out of the ephemeral container into GENERATED_DIR before the container expires.

        Guardrails:
        - Hard-cap MAX_GENERATED_FILES_PER_TURN files per turn (drops any extras).
        - Reject any individual file larger than MAX_GENERATED_FILE_BYTES.
        - Normalise filenames via Path(...).name to block directory traversal.
        """
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
                if len(out) >= MAX_GENERATED_FILES_PER_TURN:
                    log.info("file cap reached, dropping remaining file_id=%s", fid)
                    continue
                try:
                    meta = self.client.beta.files.retrieve_metadata(fid)
                    declared = getattr(meta, "size_bytes", None) or getattr(meta, "size", None)
                    if declared and declared > MAX_GENERATED_FILE_BYTES:
                        out.append({"file_id": fid, "filename": "oversize",
                                    "size": 0,
                                    "error": f"file exceeds {MAX_GENERATED_FILE_BYTES} bytes"})
                        continue
                    blob = self.client.beta.files.download(fid)
                    filename = getattr(meta, "filename", None) or f"{fid}.bin"
                    safe_name = Path(filename).name or f"{fid}.bin"
                    dest = GENERATED_DIR / f"{fid}_{safe_name}"
                    blob.write_to_file(str(dest))
                    size = dest.stat().st_size
                    if size > MAX_GENERATED_FILE_BYTES:
                        # Defence-in-depth: delete if download exceeds cap.
                        try:
                            dest.unlink()
                        except OSError:
                            pass
                        out.append({"file_id": fid, "filename": safe_name,
                                    "size": 0,
                                    "error": f"file exceeds {MAX_GENERATED_FILE_BYTES} bytes"})
                        continue
                    out.append({
                        "file_id": fid,
                        "filename": safe_name,
                        "size": size,
                    })
                except Exception as exc:
                    out.append({"file_id": fid, "filename": "unknown", "size": 0,
                                "error": str(exc)})
        return out
