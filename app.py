"""FastAPI app: SSE chat + rate limits + daily budget + JSON logs + /metrics."""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import mimetypes

import httpx
import secrets
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, generate_latest
from pydantic import BaseModel, Field
from typing import Literal, Optional

from agent import ChatAgent
from guardrails import scrub_response
from limits import DAILY_BUDGET_USD, Limits, estimate_cost_usd
from model_router import MODEL_HAIKU, MODEL_OPUS, MODEL_SONNET
from response_cleaner import (
    detect_file_intent_leak,
    out_of_range_refusal,
    user_msg_requested_file,
)

TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str, ip: str) -> bool:
    if not TURNSTILE_SECRET:
        return True
    if not token:
        return False
    try:
        resp = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": TURNSTILE_SECRET, "response": token, "remoteip": ip},
            timeout=5.0,
        )
        return bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError, KeyError):
        return False

load_dotenv()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for k in ("request_id", "ip", "outcome", "latency_ms",
                  "tokens_in", "tokens_out", "cost_usd", "history_len", "user_msg",
                  "channel", "external_user_id"):
            v = getattr(record, k, None)
            if v is not None:
                obj[k] = v
        return json.dumps(obj)


_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger("chatbot")

STATIC_DIR = Path(__file__).parent / "static"
GENERATED_DIR = Path(os.getenv("CHATBOT_GENERATED_DIR", "/opt/chatbot/app/generated"))
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
PORT = int(os.getenv("CHATBOT_PORT", "8083"))

PREBUILT_PATH = STATIC_DIR / "prebuilt_answers.json"
try:
    PREBUILT_ANSWERS = json.loads(PREBUILT_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    PREBUILT_ANSWERS = {}


# Smart-quote / dash translation table applied before normalisation. iOS,
# macOS, and Word silently swap straight ASCII quotes/dashes for typographic
# variants — without this, the prebuilt cache misses every iOS user who
# pastes the chip.
_NORM_TRANSLATE = str.maketrans({
    "‘": "'",  # left single quote
    "’": "'",  # right single quote (most common iOS substitution)
    "‚": "'",  # single low-9 quote
    "‛": "'",  # high-reversed-9
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',  # double low-9
    "‟": '"',  # double high-reversed-9
    "–": "-",  # en dash
    "—": "-",  # em dash
    "−": "-",  # minus sign
})

# Trailing punctuation we strip so "What's the date range" matches
# "What's the date range?" / "What's the date range." / etc.
_TRAILING_PUNCT = ".?!;,:"

# Common English contractions expanded BEFORE the lowercase / whitespace /
# trailing-punct passes in `_norm`. Without this, "What is in this data?"
# misses the cache while "What's in this data?" hits — same intent, two
# code paths, double the spend. Keys are lowercase + smart-quote-normalised
# (matching the order of operations in `_norm`).
_CONTRACTIONS = {
    "what's": "what is",
    "it's": "it is",
    "we're": "we are",
    "don't": "do not",
    "can't": "cannot",
    "won't": "will not",
    "there's": "there is",
    "that's": "that is",
    "i'm": "i am",
    "you're": "you are",
    "they're": "they are",
    "i've": "i have",
    "i'll": "i will",
    "let's": "let us",
}
# Word-boundary regex so "what's" matches but "whats" (no apostrophe) does
# not — the apostrophe-stripped fallback handles that case separately.
_CONTRACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _CONTRACTIONS) + r")\b"
)


def _expand_contractions(s: str) -> str:
    """Expand common English contractions on a lowercased string."""
    return _CONTRACTION_RE.sub(lambda m: _CONTRACTIONS[m.group(1)], s)


def _norm(s: str) -> str:
    """Aggressive normalisation for prebuilt-cache lookup.

    Handles: case, internal whitespace runs, smart-quote substitutions
    (iOS / Word), em/en dashes, trailing punctuation, and common English
    contraction expansion ("what's" ↔ "what is"). The apostrophe-strip
    variant ("whats" vs "what's") is a separate fallback handled at lookup
    time — see ``_norm_no_apostrophe`` below.

    Order: smart-quote translate → lowercase → contraction expansion →
    whitespace collapse → trailing-punct strip. Contractions are expanded
    AFTER lowercase (the table is keyed on lowercase forms) but BEFORE
    whitespace collapse so the resulting "what is" doesn't introduce
    double-space artefacts.
    """
    s = s.translate(_NORM_TRANSLATE)
    s = s.lower()
    s = _expand_contractions(s)
    s = " ".join(s.split())
    while s and s[-1] in _TRAILING_PUNCT:
        s = s[:-1].rstrip()
    return s


def _norm_no_apostrophe(s: str) -> str:
    """Same as ``_norm`` but with all apostrophes removed. Used as a fallback
    so a user who types "whats driving it" still matches a chip whose
    canonical form is "what's driving it"."""
    return _norm(s).replace("'", "")


_PAN_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0 and len(digits) >= 13


def redact_pan(text: str) -> tuple[str, int]:
    """Redact any Luhn-valid 13-19 digit sequence from text.

    Returns (redacted_text, count_of_redactions). Used on all inbound user
    text (web + Twilio) so a real PAN pasted by a user never reaches chat
    history, logs, or the Anthropic API.
    """
    if not text:
        return text, 0
    count = 0

    def _sub(m: re.Match) -> str:
        nonlocal count
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            count += 1
            return "[REDACTED_PAN]"
        return m.group(0)

    return _PAN_CANDIDATE_RE.sub(_sub, text), count


PREBUILT_ALIASES = {
    # Legacy v1 alias carried forward.
    "Our cost of payments went up this quarter. What's driving it, and how much of it can we actually fix?":
        "Our cost of payments went up by 2% this quarter. What's driving it, and how much of it can we actually fix?",

    # v2 introspection aliases (adversarial report 2026-04-24). Six Opus-4.7
    # prebuilts sit in prebuilt_answers.json but are NOT on the homepage
    # chip strip — a user who types any semantic rephrasing of "what
    # dataset is this", "which PSPs", "what's the date range",
    # "retry recovery", "network token vs PAN", "cross-border vs
    # domestic" will hit the canned answer instead of burning $ on a
    # live-LLM round trip. Exact-string match first, then normalised.
    # The canonical RHS is verbatim the prebuilt key.
    "What dataset is this?": "What dataset am I asking about?",
    "What dataset are we looking at?": "What dataset am I asking about?",
    "Tell me about the dataset": "What dataset am I asking about?",
    "What's in this data?": "What dataset am I asking about?",
    "What data do you have?": "What dataset am I asking about?",
    "What's the data?": "What dataset am I asking about?",
    "Describe the dataset": "What dataset am I asking about?",

    "What PSPs are in the data?": "Which PSPs are in the data?",
    "Which processors do we use?": "Which PSPs are in the data?",
    "What processors are in the data?": "Which PSPs are in the data?",
    "Which acquirers are in the data?": "Which PSPs are in the data?",
    "List the PSPs": "Which PSPs are in the data?",
    "Who are our processors?": "Which PSPs are in the data?",

    "What is the date range of the dataset?": "What's the date range of the dataset?",
    "What dates does the data cover?": "What's the date range of the dataset?",
    "What time period is this?": "What's the date range of the dataset?",
    "How far back does the data go?": "What's the date range of the dataset?",
    "When does the data start and end?": "What's the date range of the dataset?",

    "What is the retry recovery rate?": "What's the retry recovery rate?",
    "How good are our retries?": "What's the retry recovery rate?",
    "What's our retry success rate?": "What's the retry recovery rate?",
    "What is our retry success rate?": "What's the retry recovery rate?",

    "What is the network-token vs PAN approval difference?": "What's the network-token vs PAN approval difference?",
    "Network token vs PAN approval?": "What's the network-token vs PAN approval difference?",
    "Do network tokens lift approval?": "What's the network-token vs PAN approval difference?",
    "What's the token lift?": "What's the network-token vs PAN approval difference?",

    "What is the approval-rate difference between cross-border and domestic transactions?": "What's the approval-rate difference between cross-border and domestic transactions?",
    "Cross-border vs domestic approval?": "What's the approval-rate difference between cross-border and domestic transactions?",
    "What's the cross-border approval gap?": "What's the approval-rate difference between cross-border and domestic transactions?",
    "How does cross-border approval compare to domestic?": "What's the approval-rate difference between cross-border and domestic transactions?",
}
for alias, canonical in PREBUILT_ALIASES.items():
    if canonical in PREBUILT_ANSWERS:
        PREBUILT_ANSWERS[alias] = PREBUILT_ANSWERS[canonical]

PREBUILT_NORMALIZED = {_norm(k): v for k, v in PREBUILT_ANSWERS.items()}
# Apostrophe-stripped fallback so "Whats driving it" matches a chip whose
# canonical key is "What's driving it".
PREBUILT_NORM_NO_APOS = {_norm_no_apostrophe(k): v for k, v in PREBUILT_ANSWERS.items()}
PREBUILT_DELAY_SEC = float(os.getenv("PREBUILT_DELAY_SEC", "3"))


def _lookup_prebuilt(message: str) -> str | None:
    """Symmetric prebuilt-cache lookup.

    Order:
      1. Exact-string match on the raw user message.
      2. Normalised match (case + whitespace + smart-quotes + dashes +
         trailing-punct).
      3. Apostrophe-strip fallback (handles "whats" → "what's").

    Returns the prebuilt answer string, or ``None`` to fall through to the
    live LLM path.
    """
    if not message:
        return None
    raw = message.strip()
    hit = PREBUILT_ANSWERS.get(raw)
    if hit:
        return hit
    hit = PREBUILT_NORMALIZED.get(_norm(raw))
    if hit:
        return hit
    return PREBUILT_NORM_NO_APOS.get(_norm_no_apostrophe(raw))

agent = ChatAgent()
limits = Limits()

METRICS = CollectorRegistry()
req_counter = Counter(
    "chatbot_requests_total", "Total chat requests", ["outcome"], registry=METRICS
)
tok_counter = Counter(
    "chatbot_tokens_total", "Total tokens consumed", ["kind"], registry=METRICS
)
cost_counter = Counter(
    "chatbot_cost_usd_total", "Cumulative API spend in USD", registry=METRICS
)
budget_gauge = Gauge(
    "chatbot_budget_remaining_usd", "Remaining daily budget in USD", registry=METRICS
)
# File-generation tracking (plan §3, step 5). `format` is the file
# extension (pdf|xlsx|csv|png|other); `outcome` is one of:
#   ok                 — file SSE event emitted on first or retry pass
#   failed_first_try   — user requested a file, model leaked intent, retry triggered
#   failed_after_retry — retry also produced no file
#   retried_ok         — retry succeeded after first-try miss
chatbot_files_generated_total = Counter(
    "chatbot_files_generated_total",
    "Files generated by the chatbot",
    ["format", "outcome"],
    registry=METRICS,
)


def _file_format_label(filename: str) -> str:
    """Map a filename to a metric label (pdf|xlsx|csv|png|other)."""
    if not filename:
        return "other"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("pdf", "xlsx", "csv", "png"):
        return ext
    return "other"


# Janitor for the GENERATED_DIR — deletes files older than 24h, hard-caps
# total directory size at 500 MB. Runs at startup and opportunistically
# every JANITOR_RUN_EVERY_N_REQUESTS chat turns. Plan §5.1.
GENERATED_MAX_AGE_SECONDS = int(os.getenv("CHATBOT_GENERATED_MAX_AGE_SECONDS", "86400"))
GENERATED_MAX_DIR_BYTES = int(os.getenv("CHATBOT_GENERATED_MAX_DIR_BYTES", str(500 * 1024 * 1024)))
JANITOR_RUN_EVERY_N_REQUESTS = int(os.getenv("CHATBOT_JANITOR_EVERY_N", "100"))
_janitor_request_counter = {"n": 0}


def _run_generated_janitor() -> dict:
    """Delete old files and enforce the size cap. Returns a small stats dict."""
    deleted_age = 0
    deleted_size = 0
    bytes_freed = 0
    try:
        now = time.time()
        files: list[tuple[Path, float, int]] = []
        for p in GENERATED_DIR.iterdir():
            try:
                if not p.is_file():
                    continue
                st = p.stat()
                files.append((p, st.st_mtime, st.st_size))
            except OSError:
                continue
        # 1. Age-based deletion.
        survivors: list[tuple[Path, float, int]] = []
        for p, mtime, size in files:
            if now - mtime > GENERATED_MAX_AGE_SECONDS:
                try:
                    p.unlink()
                    deleted_age += 1
                    bytes_freed += size
                except OSError:
                    survivors.append((p, mtime, size))
            else:
                survivors.append((p, mtime, size))
        # 2. Size-cap enforcement: drop oldest until under the cap.
        total = sum(s for _, _, s in survivors)
        if total > GENERATED_MAX_DIR_BYTES:
            survivors.sort(key=lambda t: t[1])  # oldest first
            for p, mtime, size in survivors:
                if total <= GENERATED_MAX_DIR_BYTES:
                    break
                try:
                    p.unlink()
                    deleted_size += 1
                    bytes_freed += size
                    total -= size
                except OSError:
                    continue
    except Exception:  # noqa: BLE001 — janitor must never raise
        log.exception("janitor failed")
    if deleted_age or deleted_size:
        log.info("generated janitor",
                 extra={"outcome": "janitor",
                        "user_msg": f"deleted_age={deleted_age} "
                                    f"deleted_size={deleted_size} "
                                    f"bytes_freed={bytes_freed}"})
    return {"deleted_age": deleted_age, "deleted_size": deleted_size,
            "bytes_freed": bytes_freed}


def _maybe_run_janitor() -> None:
    _janitor_request_counter["n"] += 1
    if _janitor_request_counter["n"] >= JANITOR_RUN_EVERY_N_REQUESTS:
        _janitor_request_counter["n"] = 0
        _run_generated_janitor()


HERO_FALLBACK = """**Daily demo budget reached.**

Live analysis resumes tomorrow (budget resets at 00:00 UTC).
"""

# v5 audit N4 (2026-04-27): single-line synthetic-data disclaimer that
# the /chat event_stream prepends to the first text chunk of every live
# LLM response. Wave 3B B4 added this prefix to prebuilt answers; live
# answers were missing it, so users were seeing synthetic dollar figures
# without framing. Mirrors the prebuilt phrasing for visual consistency.
SYNTHETIC_DISCLAIMER = "_Figures are from the synthetic 100K-row sample dataset._\n\n"


# Tier-switch intent detector (added 2026-04-27 with the tier-selector
# buttons). A user typing "switch to opus" / "use haiku" / "set model to
# sonnet" / "run faster" used to hit the live LLM, which interpreted the
# off-topic message as a vague directive about the attached CSV file and
# replied with a non-sequitur ("I'm now working from transactions.csv —
# what would you like to dig into?"). We now intercept these phrases up
# front and point the user to the new tier-selector buttons in the UI.
_TIER_SWITCH_RE = re.compile(
    r"^\s*(?:please\s+)?"
    r"(?:switch|use|set|run|select|change|pick|choose|go|model)"
    r"(?:\s+(?:to|the|model|tier|with|on))*\s+"
    r"(haiku|sonnet|opus|fast(?:er)?|slow(?:er)?|cheap(?:er)?|"
    r"quick(?:er)?|complex|thinking|better|deep(?:er)?|smart(?:er)?)"
    r"(?:\s+(?:model|tier|mode|please))?\s*[.!?]?\s*$",
    re.IGNORECASE,
)
TIER_SWITCH_HINT = (
    "Use the **Faster / Default / Better thinking** buttons just above "
    "the chat input to pick a model. \"Faster\" is Haiku (cheap, quick "
    "lookups), \"Default\" auto-routes (Sonnet for most questions, Opus "
    "for multi-hop / forecasts), and \"Better thinking\" forces Opus "
    "(slower, deeper reasoning). The selection sticks across messages "
    "until you click another button."
)


def detect_tier_switch_intent(message: str) -> bool:
    """Return ``True`` if the user is trying to change the model tier in
    natural language (so we can route them to the UI buttons rather than
    burning a live-LLM call on an off-topic directive)."""
    if not message:
        return False
    return bool(_TIER_SWITCH_RE.match(message.strip()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Uploading CSV to Anthropic Files API...")
    file_id = agent.upload_csv()
    log.info("CSV uploaded: file_id=%s", file_id)
    budget_gauge.set(limits.budget_remaining_usd())
    # Sweep the generated/ dir on startup so a long-running deploy doesn't
    # hold onto stale chips.
    stats = _run_generated_janitor()
    log.info("startup janitor",
             extra={"outcome": "startup_janitor",
                    "user_msg": f"deleted_age={stats['deleted_age']} "
                                f"deleted_size={stats['deleted_size']} "
                                f"bytes_freed={stats['bytes_freed']}"})
    yield


app = FastAPI(lifespan=lifespan)


# Inbound payload-size cap on the user message. Real CFO chips top out
# around ~250 chars; an 8K cap is generous headroom for a paste-from-deck
# question while shutting down 14 KB / 500 KB abusive payloads (v4 audit
# B3 / N7, 2026-04-26). FastAPI returns a 422 with a structured Pydantic
# error body — clients see "ensure this value has at most 8000 characters".
CHAT_MESSAGE_MAX_CHARS = int(os.getenv("CHATBOT_MESSAGE_MAX_CHARS", "8000"))


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=CHAT_MESSAGE_MAX_CHARS)
    history: list[dict] = []
    turnstile_token: str = ""
    # Tier-selector buttons (added 2026-04-27). When set, the auto-router
    # is bypassed and the named tier is used. ``None`` (default) keeps the
    # regex classifier behaviour. Anything outside the allow-list is
    # rejected by Pydantic with a 422.
    tier: Optional[Literal["haiku", "sonnet", "opus"]] = None


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# Average $ cost per answered query, used to project how many queries are
# left in today's $5 budget. Calibrated from observed Sonnet 4.6 runs: ~65
# queries per day at DAILY_BUDGET_USD = 5.00 ⇒ ~$0.077/query.
AVG_COST_PER_QUERY_USD = DAILY_BUDGET_USD / 65.0


DAILY_QUERY_BUDGET = 65


def _budget_remaining_payload() -> dict:
    """JSON-safe dict that every /chat response includes so the client can
    render the 'Demo credit: X of 65 remaining today' banner.

    Both fields are in the SAME unit (queries-per-day). v5 audit N5
    (2026-04-27) caught the prior version returning
    `{"budget_remaining": 178, "budget_total": 65}` when spent_today_usd
    was negative — `remaining` was derived from the dollar headroom
    without an upper clamp, so a negative spend printed remaining > total.
    Fixed by:
      1. Clamping budget_remaining_usd at the source (limits.py).
      2. Clamping query count to [0, DAILY_QUERY_BUDGET] here too.
    """
    remaining_usd = limits.budget_remaining_usd()
    remaining_queries = int(remaining_usd // AVG_COST_PER_QUERY_USD)
    remaining_queries = max(0, min(DAILY_QUERY_BUDGET, remaining_queries))
    exhausted = limits.budget_exhausted() or remaining_queries <= 0
    return {
        "budget_remaining": remaining_queries,
        "budget_total": DAILY_QUERY_BUDGET,
        "budget_exhausted": exhausted,
    }


def _public_health_payload() -> dict:
    """Public health body. NEVER includes budget fields — those leak the
    daily-cap dollar amount and remaining headroom, which is competitive
    intel for prompt-injection abuse / DoS budget exhaustion attacks (v4
    audit B2 / N6, 2026-04-26).

    NEVER includes model_* fields either — those leak which Anthropic
    model IDs we route to, which lets an attacker pick a prompt-injection
    payload tuned to that model family / version, and lets a competitor
    track our model spend tier. v5 audit N3 (2026-04-27): the prior
    public payload was leaking model_default/sonnet/opus/haiku — moved
    to /admin/health only.
    """
    return {
        "ok": True,
        "file_uploaded": agent.file_id is not None,
    }


def _admin_health_model_payload() -> dict:
    """Model-tier metadata that lives ONLY on the auth-protected
    /admin/health endpoint. Keeps the same date-suffix-stripped surface
    the dashboard / ops scrapers used pre-v5 so nothing breaks for
    authenticated callers."""
    return {
        "model_default": _strip_model_date(MODEL_SONNET),
        "model_haiku": _strip_model_date(MODEL_HAIKU),
        "model_sonnet": _strip_model_date(MODEL_SONNET),
        "model_opus": _strip_model_date(MODEL_OPUS),
    }


# Strip a trailing -YYYYMMDD date suffix from an Anthropic model ID so the
# /health response shows the same family-name format across haiku / sonnet
# / opus. Without this haiku is "claude-haiku-4-5-20251001" while sonnet
# and opus appear as "claude-sonnet-4-6" / "claude-opus-4-7" — a
# user-facing inconsistency flagged by v4 audit B5 / N11.
_MODEL_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")


def _strip_model_date(model_id: str) -> str:
    return _MODEL_DATE_SUFFIX_RE.sub("", model_id) if model_id else model_id


@app.get("/health")
def health() -> dict:
    """Public health endpoint. Budget fields intentionally omitted — see
    `/admin/health` for the auth-protected variant with budget telemetry."""
    return _public_health_payload()


# ---------------------------- /admin/health auth ----------------------------
#
# Mirrors the /metrics auth pattern. The admin-only health endpoint
# returns the public payload PLUS budget telemetry (remaining USD, daily
# cap). Same env vars + default-credential warning as /metrics, but a
# distinct user/password pair so an ops user can scrape budget without
# unlocking the full Prometheus surface.
#
_HEALTH_AUTH_DEFAULT_USER = "health"
_HEALTH_AUTH_DEFAULT_PASSWORD = "CHANGE_ME_IN_PRODUCTION"
_HEALTH_USER = os.getenv("CHATBOT_HEALTH_USER", _HEALTH_AUTH_DEFAULT_USER)
_HEALTH_PASSWORD = os.getenv("CHATBOT_HEALTH_PASSWORD", _HEALTH_AUTH_DEFAULT_PASSWORD)
_HEALTH_USING_DEFAULTS = (
    _HEALTH_USER == _HEALTH_AUTH_DEFAULT_USER
    and _HEALTH_PASSWORD == _HEALTH_AUTH_DEFAULT_PASSWORD
)
if _HEALTH_USING_DEFAULTS:
    log.warning(
        "admin/health endpoint using default credentials — set "
        "CHATBOT_HEALTH_USER and CHATBOT_HEALTH_PASSWORD env vars",
    )

_health_auth = HTTPBasic(realm="admin-health", auto_error=False)


def _require_health_auth(
    creds: HTTPBasicCredentials | None = Depends(_health_auth),
) -> str:
    if creds is None:
        raise HTTPException(
            status_code=401,
            detail="admin health requires authentication",
            headers={"WWW-Authenticate": 'Basic realm="admin-health"'},
        )
    user_ok = secrets.compare_digest(creds.username, _HEALTH_USER)
    pass_ok = secrets.compare_digest(creds.password, _HEALTH_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="admin-health"'},
        )
    return creds.username


@app.get("/admin/health")
def admin_health(_user: str = Depends(_require_health_auth)) -> dict:
    """Auth-protected health endpoint. Returns the public payload plus
    model-tier IDs and budget telemetry (remaining USD + daily cap).
    The model_* fields used to live on the public path; v5 audit N3
    moved them here to stop leaking model fingerprints."""
    return {
        **_public_health_payload(),
        **_admin_health_model_payload(),
        "budget_remaining_usd": round(limits.budget_remaining_usd(), 4),
        "budget_daily_usd": DAILY_BUDGET_USD,
    }


# ---------------------------- /metrics auth ---------------------------------
#
# Prometheus exposition was previously open to the world — anyone could
# read request counts, token totals, USD spend, and remaining daily
# budget by hitting `https://ivanantonov.com/chatbot/metrics`. CISO-fail.
#
# We now require HTTP Basic auth. Credentials come from environment vars
# set on the droplet's systemd unit; if they're not set the endpoint
# falls back to a hard-coded default that logs a WARNING on every hit so
# nobody ships this to prod by accident.
#
# Configure on the droplet:
#   /etc/systemd/system/chatbot.service →
#     Environment=CHATBOT_METRICS_USER=metrics
#     Environment=CHATBOT_METRICS_PASSWORD=<long-random>
#
_METRICS_AUTH_DEFAULT_USER = "metrics"
_METRICS_AUTH_DEFAULT_PASSWORD = "CHANGE_ME_IN_PRODUCTION"
_METRICS_USER = os.getenv("CHATBOT_METRICS_USER", _METRICS_AUTH_DEFAULT_USER)
_METRICS_PASSWORD = os.getenv("CHATBOT_METRICS_PASSWORD", _METRICS_AUTH_DEFAULT_PASSWORD)
_METRICS_USING_DEFAULTS = (
    _METRICS_USER == _METRICS_AUTH_DEFAULT_USER
    and _METRICS_PASSWORD == _METRICS_AUTH_DEFAULT_PASSWORD
)
if _METRICS_USING_DEFAULTS:
    log.warning(
        "metrics endpoint using default credentials — set "
        "CHATBOT_METRICS_USER and CHATBOT_METRICS_PASSWORD env vars",
    )

_metrics_auth = HTTPBasic(realm="metrics", auto_error=False)


def _require_metrics_auth(
    creds: HTTPBasicCredentials | None = Depends(_metrics_auth),
) -> str:
    """Reject /metrics requests without valid HTTP Basic credentials.

    Uses ``secrets.compare_digest`` so the comparison is constant-time
    (no username-/password-length oracle). Returns the authenticated
    username on success; raises 401 with a ``WWW-Authenticate`` header on
    failure so curl/Prometheus scrapers know to retry with creds.
    """
    if creds is None:
        raise HTTPException(
            status_code=401,
            detail="metrics requires authentication",
            headers={"WWW-Authenticate": 'Basic realm="metrics"'},
        )
    user_ok = secrets.compare_digest(creds.username, _METRICS_USER)
    pass_ok = secrets.compare_digest(creds.password, _METRICS_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="metrics"'},
        )
    return creds.username


@app.get("/metrics")
def metrics(_user: str = Depends(_require_metrics_auth)) -> PlainTextResponse:
    budget_gauge.set(limits.budget_remaining_usd())
    return PlainTextResponse(generate_latest(METRICS), media_type=CONTENT_TYPE_LATEST)


@app.get("/budget")
def budget() -> dict:
    """Lightweight GET endpoint the client hits on page load so the banner
    shows the current demo-credit count before the first chat message."""
    return _budget_remaining_payload()


def _stream_with_retry(req: "ChatRequest", request_id: str, ip: str):
    """Wrap agent.stream_answer with a one-shot retry when the user asks for
    a file, the model leaks intent ("Let me build the Excel..."), but no
    file SSE event fires. The retry adds a forcing nudge that tells the
    model to actually invoke code_execution.

    Yields the same chunks as agent.stream_answer. Retry chunks are tagged
    with ``__retry__: True`` on file events so the metrics path can label
    them ``retried_ok``. Plan §3 (architecture C) + step 4.
    """
    # Pass-through cache. We also accumulate text + track the file flag.
    first_pass_text = ""
    file_emitted_first = False
    chunks_buffered: list[dict] = []
    tier_override = getattr(req, "tier", None)
    for chunk in agent.stream_answer(
        req.history, req.message, tier_override=tier_override,
    ):
        if chunk["type"] == "text":
            first_pass_text += chunk["content"]
        elif chunk["type"] == "file":
            if not chunk.get("error") and chunk.get("size"):
                file_emitted_first = True
        chunks_buffered.append(chunk)
        yield chunk

    # Decide on retry. Only triggers when:
    #  - user explicitly asked for a file (regex on req.message), AND
    #  - the model narrated intent ("Let me build the Excel..."), AND
    #  - no successful file event was emitted in the first pass.
    if file_emitted_first:
        return
    if not user_msg_requested_file(req.message):
        return
    if not detect_file_intent_leak(first_pass_text):
        return

    # Track the retry trigger before the second pass — even if the retry
    # also fails we want to observe how often we hit this branch.
    chatbot_files_generated_total.labels(
        format="other", outcome="failed_first_try",
    ).inc()

    log.info("file-generation retry triggered",
             extra={"request_id": request_id, "ip": ip,
                    "outcome": "file_retry",
                    "user_msg": req.message.strip()[:120]})

    # Surface a brief notice to the user so the extra latency is explained.
    yield {"type": "text",
           "content": "\n\n_(Retrying — file generation didn't fire on first pass…)_\n\n"}

    # Build the nudge history. Append the original user message + the
    # model's first-pass response, then a forcing nudge as a fresh user
    # turn that demands code_execution.
    nudge_history = list(req.history) + [
        {"role": "user", "content": req.message},
        {"role": "assistant", "content": first_pass_text or "(no text)"},
    ]
    nudge_text = (
        "You said you would create the file but didn't actually call "
        "the code_execution tool. Call code_execution NOW with concrete "
        "pandas / matplotlib / openpyxl / reportlab code that saves the "
        "requested file to /tmp/<descriptive_name>.<ext>. Do not narrate "
        "intent. Execute the tool."
    )
    for chunk in agent.stream_answer(
        nudge_history, nudge_text, tier_override=tier_override,
    ):
        # Tag any file event so metrics can label as retried_ok.
        if chunk["type"] == "file":
            chunk["__retry__"] = True
        yield chunk


@app.post("/chat")
def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    request_id = uuid.uuid4().hex[:12]
    ip = _client_ip(request)
    start = time.time()

    if not req.message.strip():
        req_counter.labels(outcome="empty").inc()
        raise HTTPException(400, "empty message")

    req.message, _pan_redactions = redact_pan(req.message)
    if _pan_redactions:
        log.info("pan redacted (web)",
                 extra={"request_id": request_id, "ip": ip,
                        "outcome": "pan_redacted"})

    if not verify_turnstile(req.turnstile_token, ip):
        req_counter.labels(outcome="turnstile_failed").inc()
        log.info("turnstile failed", extra={"request_id": request_id, "ip": ip,
                                            "outcome": "turnstile_failed"})
        return StreamingResponse(
            iter([_sse({"type": "error",
                        "content": "Verification failed. Refresh the page and try again."}),
                  _sse({"type": "done"})]),
            media_type="text/event-stream",
        )

    if limits.session_over_cap(req.history):
        req_counter.labels(outcome="session_cap").inc()
        log.info("session cap hit", extra={"request_id": request_id, "ip": ip,
                                           "history_len": len(req.history),
                                           "outcome": "session_cap"})
        return StreamingResponse(
            iter([_sse({"type": "error",
                        "content": "Session limit reached (10 questions). Refresh the page to start a new session."}),
                  _sse({"type": "done"})]),
            media_type="text/event-stream",
        )

    if not limits.check_rate(ip):
        # Honour the architecture-tradeoffs page contract: per-IP sliding
        # window of 10 req / 60s returns HTTP 429 with a Retry-After
        # header. Older clients that read the SSE stream still get a
        # human-readable error chunk in the body.
        req_counter.labels(outcome="rate_limited").inc()
        log.info("rate limited", extra={"request_id": request_id, "ip": ip,
                                        "outcome": "rate_limited"})
        sse_body = (
            _sse({"type": "error",
                  "content": "Rate limit: 10 requests per minute. Try again shortly."})
            + _sse({"type": "done"})
        )
        return Response(
            content=sse_body,
            status_code=429,
            media_type="text/event-stream",
            headers={"Retry-After": "60"},
        )

    # Tier-switch intent: short-circuit before the live LLM so users don't
    # see the file-upload non-sequitur on "switch to opus" / "use haiku".
    if detect_tier_switch_intent(req.message):
        req_counter.labels(outcome="tier_switch_hint").inc()
        log.info("tier-switch hint served",
                 extra={"request_id": request_id, "ip": ip,
                        "outcome": "tier_switch_hint",
                        "user_msg": req.message.strip()[:120],
                        "latency_ms": int((time.time() - start) * 1000)})

        def tier_switch_stream():
            yield _sse({"type": "text", "content": TIER_SWITCH_HINT})
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})

        return StreamingResponse(tier_switch_stream(), media_type="text/event-stream")

    prebuilt = _lookup_prebuilt(req.message)
    if prebuilt:
        req_counter.labels(outcome="prebuilt").inc()
        log.info("prebuilt answer served",
                 extra={"request_id": request_id, "ip": ip,
                        "outcome": "prebuilt",
                        "latency_ms": int((time.time() - start) * 1000)})
        def prebuilt_stream():
            time.sleep(PREBUILT_DELAY_SEC)
            chunk_size = 120
            for i in range(0, len(prebuilt), chunk_size):
                yield _sse({"type": "text", "content": prebuilt[i:i+chunk_size]})
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})
        return StreamingResponse(prebuilt_stream(), media_type="text/event-stream")

    # Hard-refuse queries that target a date outside 2023-01-01 → 2025-12-31
    # or request a future forecast. Keeps us from burning budget on the
    # adversarial report's F2/F10 fabrication class.
    refusal = out_of_range_refusal(req.message)
    if refusal:
        req_counter.labels(outcome="out_of_range_refusal").inc()
        log.info("out-of-range refusal",
                 extra={"request_id": request_id, "ip": ip,
                        "outcome": "out_of_range_refusal",
                        "latency_ms": int((time.time() - start) * 1000),
                        "user_msg": req.message.strip()[:120]})
        def refusal_stream():
            yield _sse({"type": "text", "content": refusal})
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})
        return StreamingResponse(refusal_stream(), media_type="text/event-stream")

    if limits.budget_exhausted():
        req_counter.labels(outcome="budget_exhausted").inc()
        log.info("budget exhausted - hero fallback",
                 extra={"request_id": request_id, "ip": ip,
                        "outcome": "budget_exhausted"})
        def hero_fallback_stream():
            time.sleep(PREBUILT_DELAY_SEC)
            yield _sse({"type": "text", "content": HERO_FALLBACK})
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})
        return StreamingResponse(hero_fallback_stream(), media_type="text/event-stream")

    log.info("chat to claude",
             extra={"request_id": request_id, "ip": ip,
                    "outcome": "claude_start",
                    "user_msg": req.message.strip()[:120]})

    def event_stream():
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        # Accumulate the full text stream so the guardrail pipeline can
        # verify numeric claims / strip uncited anchors at end-of-turn.
        # The assistant may also emit its own `replace` chunk mid-stream
        # (e.g. response_cleaner.trim_last_n_days) — we track the latest
        # representation and scrub whichever the user ends up seeing.
        accumulated_text = ""
        last_replace: str | None = None
        # Track whether we successfully emitted any file SSE event this turn.
        # Used to decide whether to fire a one-shot retry when the user
        # asked for a file but the model only narrated intent.
        file_was_emitted = False
        emitted_files: list[dict] = []
        # v5 audit N4 (2026-04-27): synthetic-data disclaimer was only
        # being shipped on prebuilt answers (Wave 3B B4). Live LLM
        # responses cite synthetic dollars without framing. Prepend the
        # disclaimer on the FIRST text chunk of every live LLM turn so
        # the user always sees it before any number lands. Backend-
        # injected (vs system-prompt rule) so we don't depend on model
        # compliance and don't touch the three system-prompt patches
        # (CITATION/ARITHMETIC/SYNTHETIC) which have specific scopes.
        synthetic_disclaimer_emitted = False
        try:
            tier = "sonnet"  # default until the agent emits a model chunk
            for chunk in _stream_with_retry(req, request_id, ip):
                if chunk["type"] == "model":
                    tier = chunk.get("tier", "sonnet")
                    yield _sse({
                        "type": "model",
                        "name": chunk.get("name", "Sonnet"),
                        "label": chunk.get("label", "Sonnet"),
                        "tier": tier,
                    })
                elif chunk["type"] == "text":
                    if not synthetic_disclaimer_emitted:
                        # The disclaimer is rendered as italicised text
                        # at the very top of every live-LLM answer,
                        # mirroring the prebuilt prefix style. The
                        # trailing newlines push the model's first
                        # sentence onto its own line so the disclaimer
                        # reads as a banner, not a sentence opener.
                        synthetic_disclaimer_emitted = True
                        accumulated_text += SYNTHETIC_DISCLAIMER
                        yield _sse({"type": "text", "content": SYNTHETIC_DISCLAIMER})
                    accumulated_text += chunk["content"]
                    yield _sse({"type": "text", "content": chunk["content"]})
                elif chunk["type"] == "tool_use":
                    # Forward tool_use notifications so the UI can render
                    # "Searching the web for: <query>" while the model pauses.
                    yield _sse({"type": "tool_use",
                                "tool": chunk.get("tool", ""),
                                "query": chunk.get("query", "")})
                elif chunk["type"] == "replace":
                    # Post-processed replacement (e.g. last-N-days trim).
                    last_replace = chunk["content"]
                    yield _sse({"type": "replace", "content": chunk["content"]})
                elif chunk["type"] == "file":
                    # Skip entries where the agent failed to download the file
                    # (size=0 + error set) — don't render a broken link client-side.
                    if chunk.get("error") or not chunk.get("size"):
                        log.info("file skipped (error or empty)",
                                 extra={"request_id": request_id, "ip": ip,
                                        "outcome": "file_skipped"})
                        continue
                    file_was_emitted = True
                    fmt = _file_format_label(chunk.get("filename", ""))
                    emitted_files.append({"format": fmt,
                                          "filename": chunk.get("filename", ""),
                                          "retried": chunk.get("__retry__", False)})
                    yield _sse({
                        "type": "file",
                        "file_id": chunk["file_id"],
                        "filename": chunk["filename"],
                        "size": chunk.get("size", 0),
                        "url": f"files/{chunk['file_id']}",
                    })
                elif chunk["type"] == "usage":
                    tokens_in += chunk["input_tokens"]
                    tokens_out += chunk["output_tokens"]
                    # Price by the tier the router selected so total-spend
                    # tracking stays correct across Haiku / Sonnet / Opus.
                    # Add $0.01/web_search call on top (Anthropic billing).
                    turn_cost = estimate_cost_usd(
                        chunk["input_tokens"], chunk["output_tokens"],
                        cache_read=chunk["cache_read_input_tokens"],
                        cache_write=chunk["cache_creation_input_tokens"],
                        tier=chunk.get("tier", tier),
                        web_search_requests=chunk.get("web_search_requests", 0),
                    )
                    cost += turn_cost
                    limits.add_cost(turn_cost)
                    tok_counter.labels(kind="input").inc(chunk["input_tokens"])
                    tok_counter.labels(kind="output").inc(chunk["output_tokens"])
                    cost_counter.inc(turn_cost)
                    budget_gauge.set(limits.budget_remaining_usd())
            # Update file-generation Prometheus counter for emitted files.
            for entry in emitted_files:
                outcome = "retried_ok" if entry["retried"] else "ok"
                chatbot_files_generated_total.labels(
                    format=entry["format"], outcome=outcome,
                ).inc()
            # If the user asked for a file but nothing was emitted (even
            # after the retry path inside _stream_with_retry), record the
            # final-failure case so we can monitor.
            if (not file_was_emitted
                    and user_msg_requested_file(req.message)
                    and detect_file_intent_leak(accumulated_text)):
                chatbot_files_generated_total.labels(
                    format="other", outcome="failed_after_retry",
                ).inc()
            # Run the guardrail pipeline on the final assembled text. If
            # it materially changes the response (new numeric corrections,
            # stripped uncited anchors, etc.), emit one more `replace`
            # SSE so the UI overwrites the displayed body.
            final_text = last_replace if last_replace is not None else accumulated_text
            try:
                scrubbed = scrub_response(final_text, req.message)
            except Exception:  # noqa: BLE001 — guardrail must not block done
                log.exception("guardrail scrub failed")
                scrubbed = final_text
            if scrubbed and scrubbed != final_text:
                yield _sse({"type": "replace", "content": scrubbed})
            req_counter.labels(outcome="ok").inc()
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})
            # Opportunistic janitor pass.
            _maybe_run_janitor()
            log.info("chat ok",
                     extra={"request_id": request_id, "ip": ip,
                            "outcome": "ok",
                            "latency_ms": int((time.time() - start) * 1000),
                            "tokens_in": tokens_in, "tokens_out": tokens_out,
                            "cost_usd": round(cost, 6)})
        except Exception as e:
            req_counter.labels(outcome="error").inc()
            log.exception("stream failed", extra={"request_id": request_id,
                                                  "ip": ip, "outcome": "error"})
            yield _sse({"type": "error", "content": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/files/{file_id}")
def download_file(file_id: str):
    # file_id must be an opaque Anthropic-issued token (alphanumeric +
    # underscores/dashes only) — rejects directory traversal attempts.
    if not file_id or not file_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "invalid file id")
    matches = list(GENERATED_DIR.glob(f"{file_id}_*"))
    if not matches:
        raise HTTPException(404, "file not found")
    path = matches[0].resolve()
    # Defence-in-depth: ensure the resolved path is still inside GENERATED_DIR.
    try:
        path.relative_to(GENERATED_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(400, "invalid file path") from exc
    filename = path.name.split("_", 1)[1] if "_" in path.name else path.name
    mime, _ = mimetypes.guess_type(filename)
    return FileResponse(
        path,
        filename=filename,
        media_type=mime or "application/octet-stream",
        headers={
            # Force a download instead of inline-rendering in the browser.
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/content.json")
def content():
    return FileResponse(
        STATIC_DIR / "content.json",
        media_type="application/json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/hero.jpg")
def hero_image():
    return FileResponse(STATIC_DIR / "hero.jpg", media_type="image/jpeg")

@app.get("/sample_report.pdf")
def sample_report():
    return FileResponse(STATIC_DIR / "sample_report.pdf", media_type="application/pdf")

@app.get("/architecture.svg")
def architecture_svg():
    return FileResponse(STATIC_DIR / "architecture.svg", media_type="image/svg+xml")

# architecture-tradeoffs.html route removed 2026-04-27 (page killed per user)

# ---------------------------- WhatsApp via Twilio ----------------------------

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_WHATSAPP_WEBHOOK_URL = os.getenv(
    "TWILIO_WHATSAPP_WEBHOOK_URL",
    os.getenv("TWILIO_WEBHOOK_URL", "https://ivanantonov.com/chatbot/whatsapp"),
)
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "")
TWILIO_SMS_WEBHOOK_URL = os.getenv(
    "TWILIO_SMS_WEBHOOK_URL", "https://ivanantonov.com/chatbot/sms"
)

try:
    from twilio.request_validator import RequestValidator
    from twilio.rest import Client as TwilioClient
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
    twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None
except ImportError:
    twilio_client = None
    twilio_validator = None

WA_HISTORY: dict[str, list] = {}
SMS_HISTORY: dict[str, list] = {}
WA_MAX_LEN = 20
WA_CHUNK_LIMIT = 1500


def _trim_history(hist: list, max_len: int = WA_MAX_LEN) -> None:
    """Keep at most ``max_len`` messages in-place, dropping the oldest."""
    if len(hist) > max_len:
        del hist[: len(hist) - max_len]

SMS_DAILY_LIMIT = int(os.getenv("SMS_DAILY_LIMIT", "20"))
_sms_day = {"date": None, "count": 0, "notified": False}


def _sms_check_and_inc() -> tuple[bool, bool]:
    today = datetime.now(timezone.utc).date()
    if _sms_day["date"] != today:
        _sms_day["date"] = today
        _sms_day["count"] = 0
        _sms_day["notified"] = False
    if _sms_day["count"] >= SMS_DAILY_LIMIT:
        notify = not _sms_day["notified"]
        _sms_day["notified"] = True
        return False, notify
    _sms_day["count"] += 1
    return True, False


def _history_for(from_phone: str) -> dict[str, list]:
    return WA_HISTORY if from_phone.startswith("whatsapp:") else SMS_HISTORY


def _session_key(from_phone: str, external_user_id: str) -> str:
    """Stable per-user key for conversation history and rate limiting.

    Prefers Twilio's ``ExternalUserId`` (WhatsApp BSUID, e.g.
    ``whatsapp:BR.1A2B3C...``) when present so a user who adopts a
    WhatsApp username (June 2026 rollout) keeps their thread across the
    transition: pre-adoption Twilio sends ``From=whatsapp:+E164`` plus
    ``ExternalUserId=whatsapp:CC.alphanum``; post-adoption ``From`` and
    ``ExternalUserId`` both carry the BSUID. The BSUID is stable across
    that transition, so keying on it preserves continuity.

    Falls back to ``from_phone`` for the SMS channel (no BSUID concept)
    and for any pre-rollout WhatsApp webhook where ``ExternalUserId`` is
    absent. Twilio inbound webhook population begins mid-May 2026 per
    their developer notice.
    """
    return external_user_id or from_phone


def _from_number_for(to: str) -> str:
    return TWILIO_WHATSAPP_FROM if to.startswith("whatsapp:") else TWILIO_SMS_FROM


def _channel_label(from_phone: str) -> str:
    return "whatsapp" if from_phone.startswith("whatsapp:") else "sms"


def _wa_split(text: str) -> list[str]:
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        cand = (buf + "\n\n" + para) if buf else para
        if len(cand) <= WA_CHUNK_LIMIT:
            buf = cand
            continue
        if buf:
            chunks.append(buf)
        if len(para) > WA_CHUNK_LIMIT:
            for i in range(0, len(para), WA_CHUNK_LIMIT):
                chunks.append(para[i:i + WA_CHUNK_LIMIT])
            buf = ""
        else:
            buf = para
    if buf:
        chunks.append(buf)
    return chunks


def _twilio_send(to: str, body: str) -> None:
    if not twilio_client:
        log.warning("twilio_client not configured; skipping send")
        return
    from_ = _from_number_for(to)
    if not from_:
        log.warning("no from-number configured for %s", to)
        return
    chunks = _wa_split(body)
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        # Twilio's outbound queue does not guarantee delivery order when
        # messages.create is called rapid-fire. Symptom: WhatsApp users
        # see (2/3) arrive before (1/3). Mitigations:
        #   1) Prefix multi-chunk sends with "(i/total)" so the user can
        #      mentally re-order if a race still happens.
        #   2) Sleep ~250ms between successive sends so each create call
        #      reaches Twilio's API in monotonically increasing order.
        #      Adds ~0.25s * (chunks-1) latency per multi-chunk reply.
        body_to_send = f"({i + 1}/{total}) {chunk}" if total > 1 else chunk
        try:
            twilio_client.messages.create(from_=from_, to=to, body=body_to_send)
        except Exception:  # noqa: BLE001
            log.exception("twilio send failed (chunk %d/%d, to=%s)", i + 1, total, to)
            raise
        if i < total - 1:
            time.sleep(0.25)


def _twilio_process(request_id: str, from_phone: str, external_user_id: str,
                    user_text: str) -> None:
    start = time.time()
    channel = _channel_label(from_phone)
    history = _history_for(from_phone)
    session_key = _session_key(from_phone, external_user_id)

    if channel == "sms":
        allowed, notify = _sms_check_and_inc()
        if not allowed:
            req_counter.labels(outcome="sms_daily_limit").inc()
            log.info("sms daily limit hit",
                     extra={"request_id": request_id, "ip": from_phone,
                            "external_user_id": external_user_id,
                            "outcome": "sms_daily_limit", "channel": channel})
            if notify:
                try:
                    _twilio_send(from_phone,
                                 f"Daily SMS limit ({SMS_DAILY_LIMIT}) reached. "
                                 f"Try again tomorrow, or use web chat at ivanantonov.com/chatbot.")
                except Exception:
                    pass
            return

    try:
        prebuilt = _lookup_prebuilt(user_text)
        if prebuilt:
            time.sleep(PREBUILT_DELAY_SEC)
            _twilio_send(from_phone, prebuilt)
            hist = history.setdefault(session_key, [])
            hist.append({"role": "user", "content": user_text})
            hist.append({"role": "assistant", "content": prebuilt})
            _trim_history(hist)
            req_counter.labels(outcome="prebuilt").inc()
            log.info(f"{channel} prebuilt",
                     extra={"request_id": request_id, "ip": from_phone,
                            "external_user_id": external_user_id,
                            "outcome": "prebuilt", "channel": channel,
                            "latency_ms": int((time.time() - start) * 1000)})
            return

        if limits.budget_exhausted():
            time.sleep(PREBUILT_DELAY_SEC)
            _twilio_send(from_phone, HERO_FALLBACK)
            req_counter.labels(outcome="budget_exhausted").inc()
            return

        hist = history.setdefault(session_key, [])
        _trim_history(hist)

        parts: list[str] = []
        tokens_in = tokens_out = 0
        cost = 0.0
        for chunk in agent.stream_answer(hist, user_text):
            if chunk["type"] == "text":
                parts.append(chunk["content"])
            elif chunk["type"] == "usage":
                tokens_in = chunk["input_tokens"]
                tokens_out = chunk["output_tokens"]
                cost = estimate_cost_usd(
                    tokens_in, tokens_out,
                    cache_read=chunk["cache_read_input_tokens"],
                    cache_write=chunk["cache_creation_input_tokens"],
                    tier=chunk.get("tier", "sonnet"),
                    web_search_requests=chunk.get("web_search_requests", 0),
                )
                limits.add_cost(cost)
                tok_counter.labels(kind="input").inc(tokens_in)
                tok_counter.labels(kind="output").inc(tokens_out)
                cost_counter.inc(cost)
                budget_gauge.set(limits.budget_remaining_usd())

        answer = "".join(parts).strip() or "(no response)"
        # v5 audit N4 (2026-04-27): mirror the /chat web-channel
        # disclaimer on WhatsApp / SMS so a user who consumes the bot
        # over Twilio also sees the synthetic-data framing before any
        # dollar figure. Skip if the model already led with the same
        # framing (idempotent).
        if answer != "(no response)" and "synthetic 100K-row sample" not in answer:
            answer = SYNTHETIC_DISCLAIMER.strip() + "\n\n" + answer
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": answer})
        _trim_history(hist)
        _twilio_send(from_phone, answer)
        req_counter.labels(outcome="ok").inc()
        log.info(f"{channel} ok",
                 extra={"request_id": request_id, "ip": from_phone,
                        "external_user_id": external_user_id,
                        "outcome": "ok", "channel": channel,
                        "latency_ms": int((time.time() - start) * 1000),
                        "tokens_in": tokens_in, "tokens_out": tokens_out,
                        "cost_usd": round(cost, 6)})
    except Exception as e:
        req_counter.labels(outcome="error").inc()
        log.exception(f"{channel} failed",
                      extra={"request_id": request_id, "ip": from_phone,
                             "external_user_id": external_user_id,
                             "outcome": "error", "channel": channel})
        try:
            _twilio_send(from_phone, f"Sorry, something went wrong: {e}")
        except Exception:  # noqa: BLE001 — best-effort fallback notification on an already-failed path
            pass


async def _twilio_webhook(request: Request, background: BackgroundTasks,
                          webhook_url: str, endpoint_name: str) -> Response:
    form = dict(await request.form())
    if twilio_validator:
        sig = request.headers.get("X-Twilio-Signature", "")
        if not twilio_validator.validate(webhook_url, form, sig):
            raise HTTPException(403, "invalid twilio signature")

    from_phone = form.get("From", "")
    # WhatsApp Usernames (June 2026): Twilio populates ExternalUserId with
    # the user's BSUID (whatsapp:CC.alphanum, ≤140 chars). Always present
    # for WhatsApp once Twilio's mid-May 2026 rollout completes; absent on
    # SMS and on pre-rollout webhooks. We capture it as the stable session
    # identifier — see _session_key() for the full rationale.
    external_user_id = form.get("ExternalUserId", "")
    user_text = (form.get("Body") or "").strip()
    request_id = uuid.uuid4().hex[:12]

    if not from_phone or not user_text:
        return Response(status_code=200)

    user_text, _pan_redactions = redact_pan(user_text)
    if _pan_redactions:
        log.info(f"{endpoint_name} pan redacted",
                 extra={"request_id": request_id, "ip": from_phone,
                        "external_user_id": external_user_id,
                        "outcome": "pan_redacted", "channel": endpoint_name})

    rate_key = _session_key(from_phone, external_user_id)
    if not limits.check_rate(rate_key):
        _twilio_send(from_phone, "Rate limit: 10 messages per minute. Try again shortly.")
        return Response(status_code=200)

    log.info(f"{endpoint_name} in",
             extra={"request_id": request_id, "ip": from_phone,
                    "external_user_id": external_user_id,
                    "outcome": f"{endpoint_name}_in",
                    "channel": endpoint_name,
                    "user_msg": user_text[:120]})

    background.add_task(_twilio_process, request_id, from_phone,
                        external_user_id, user_text)
    return Response(status_code=200)


@app.post("/whatsapp")
async def whatsapp(request: Request, background: BackgroundTasks) -> Response:
    return await _twilio_webhook(request, background,
                                 TWILIO_WHATSAPP_WEBHOOK_URL, "whatsapp")


@app.post("/sms")
async def sms(request: Request, background: BackgroundTasks) -> Response:
    return await _twilio_webhook(request, background,
                                 TWILIO_SMS_WEBHOOK_URL, "sms")


if __name__ == "__main__":
    import uvicorn
    # ----------------------------------------------------------------------
    # Workers / concurrency decision (v5 audit N1, 2026-04-27)
    # ----------------------------------------------------------------------
    # We deliberately stay at workers=1. Multiple uvicorn workers would
    # break correctness because per-process state is not shared:
    #   * limits.py writes /opt/chatbot/data/budget.json on every cost
    #     addition with NO inter-process file lock — workers=2 races the
    #     write and silently loses spend, which would defeat the daily cap.
    #   * agent.upload_csv() runs in the lifespan startup. With workers=2
    #     the 100K-row CSV would be uploaded to the Anthropic Files API
    #     twice, producing two divergent file_id values per worker.
    #   * In-memory rate-limit deques (`_ip_windows`), SMS daily counter
    #     (`_sms_day`), WhatsApp/SMS conversation history, prebuilt-cache,
    #     and the Prometheus registry are all per-process — they would
    #     fragment across workers.
    #
    # The v5-audit N1 30-request burst that knocked the chatbot offline
    # was real, but it is a thread-pool / file-generation latency problem
    # (sandbox file gen can run 60-180s and ties up an anyio thread for
    # each in-flight request), NOT a worker-count problem. The proper fix
    # is to make file-gen non-blocking, which is a larger refactor.
    # As short-term mitigation we could raise the anyio threadpool ceiling
    # but it must be done inside an async startup hook (sync module-load
    # has no event loop). Deferred — file-gen non-blocking refactor is
    # the proper fix.
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        # v5 audit N2 (regressed B3): hide the `Server: uvicorn` header
        # from every response so we don't fingerprint the framework /
        # version to scanners. Re-applied after a regression — verified
        # in the wave-4a redeploy.
        server_header=False,
    )
