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

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, generate_latest
from pydantic import BaseModel

from agent import ChatAgent
from limits import DAILY_BUDGET_USD, Limits, estimate_cost_usd
from response_cleaner import out_of_range_refusal

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
                  "channel"):
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


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


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
    "Our cost of payments went up this quarter. What's driving it, and how much of it can we actually fix?":
        "Our cost of payments went up by 2% this quarter. What's driving it, and how much of it can we actually fix?",
}
for alias, canonical in PREBUILT_ALIASES.items():
    if canonical in PREBUILT_ANSWERS:
        PREBUILT_ANSWERS[alias] = PREBUILT_ANSWERS[canonical]

PREBUILT_NORMALIZED = {_norm(k): v for k, v in PREBUILT_ANSWERS.items()}
PREBUILT_DELAY_SEC = float(os.getenv("PREBUILT_DELAY_SEC", "3"))

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


HERO_FALLBACK = """**Daily demo budget reached.**

Live analysis resumes tomorrow (budget resets at 00:00 UTC).
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Uploading CSV to Anthropic Files API...")
    file_id = agent.upload_csv()
    log.info("CSV uploaded: file_id=%s", file_id)
    budget_gauge.set(limits.budget_remaining_usd())
    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    turnstile_token: str = ""


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


def _budget_remaining_payload() -> dict:
    """JSON-safe dict that every /chat response includes so the client can
    render the 'Demo credit: X of 65 remaining today' banner."""
    remaining_usd = limits.budget_remaining_usd()
    remaining_queries = int(remaining_usd // AVG_COST_PER_QUERY_USD)
    exhausted = limits.budget_exhausted() or remaining_queries <= 0
    return {
        "budget_remaining": max(0, remaining_queries),
        "budget_total": 65,
        "budget_exhausted": exhausted,
    }


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "file_uploaded": agent.file_id is not None,
        "model": os.getenv("CHATBOT_MODEL", "claude-sonnet-4-6"),
        "budget_remaining_usd": round(limits.budget_remaining_usd(), 4),
        "budget_daily_usd": DAILY_BUDGET_USD,
    }


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    budget_gauge.set(limits.budget_remaining_usd())
    return PlainTextResponse(generate_latest(METRICS), media_type=CONTENT_TYPE_LATEST)


@app.get("/budget")
def budget() -> dict:
    """Lightweight GET endpoint the client hits on page load so the banner
    shows the current demo-credit count before the first chat message."""
    return _budget_remaining_payload()


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
        req_counter.labels(outcome="rate_limited").inc()
        log.info("rate limited", extra={"request_id": request_id, "ip": ip,
                                        "outcome": "rate_limited"})
        return StreamingResponse(
            iter([_sse({"type": "error",
                        "content": "Rate limit: 10 requests per minute. Try again shortly."}),
                  _sse({"type": "done"})]),
            media_type="text/event-stream",
        )

    prebuilt = PREBUILT_ANSWERS.get(req.message.strip()) or PREBUILT_NORMALIZED.get(_norm(req.message))
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
        try:
            for chunk in agent.stream_answer(req.history, req.message):
                if chunk["type"] == "text":
                    yield _sse({"type": "text", "content": chunk["content"]})
                elif chunk["type"] == "replace":
                    # Post-processed replacement (e.g. last-N-days trim).
                    yield _sse({"type": "replace", "content": chunk["content"]})
                elif chunk["type"] == "file":
                    yield _sse({
                        "type": "file",
                        "file_id": chunk["file_id"],
                        "filename": chunk["filename"],
                        "size": chunk.get("size", 0),
                        "url": f"files/{chunk['file_id']}",
                    })
                elif chunk["type"] == "usage":
                    tokens_in = chunk["input_tokens"]
                    tokens_out = chunk["output_tokens"]
                    cost = estimate_cost_usd(
                        tokens_in, tokens_out,
                        cache_read=chunk["cache_read_input_tokens"],
                        cache_write=chunk["cache_creation_input_tokens"],
                    )
                    limits.add_cost(cost)
                    tok_counter.labels(kind="input").inc(tokens_in)
                    tok_counter.labels(kind="output").inc(tokens_out)
                    cost_counter.inc(cost)
                    budget_gauge.set(limits.budget_remaining_usd())
            req_counter.labels(outcome="ok").inc()
            yield _sse({"type": "budget", **_budget_remaining_payload()})
            yield _sse({"type": "done"})
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
    if not file_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "invalid file id")
    matches = list(GENERATED_DIR.glob(f"{file_id}_*"))
    if not matches:
        raise HTTPException(404, "file not found")
    path = matches[0]
    filename = path.name.split("_", 1)[1] if "_" in path.name else path.name
    return FileResponse(path, filename=filename)


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
    for chunk in _wa_split(body):
        twilio_client.messages.create(from_=from_, to=to, body=chunk)


def _twilio_process(request_id: str, from_phone: str, user_text: str) -> None:
    start = time.time()
    channel = _channel_label(from_phone)
    history = _history_for(from_phone)

    if channel == "sms":
        allowed, notify = _sms_check_and_inc()
        if not allowed:
            req_counter.labels(outcome="sms_daily_limit").inc()
            log.info("sms daily limit hit",
                     extra={"request_id": request_id, "ip": from_phone,
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
        prebuilt = (PREBUILT_ANSWERS.get(user_text.strip())
                    or PREBUILT_NORMALIZED.get(_norm(user_text)))
        if prebuilt:
            time.sleep(PREBUILT_DELAY_SEC)
            _twilio_send(from_phone, prebuilt)
            hist = history.setdefault(from_phone, [])
            hist.append({"role": "user", "content": user_text})
            hist.append({"role": "assistant", "content": prebuilt})
            _trim_history(hist)
            req_counter.labels(outcome="prebuilt").inc()
            log.info(f"{channel} prebuilt",
                     extra={"request_id": request_id, "ip": from_phone,
                            "outcome": "prebuilt", "channel": channel,
                            "latency_ms": int((time.time() - start) * 1000)})
            return

        if limits.budget_exhausted():
            time.sleep(PREBUILT_DELAY_SEC)
            _twilio_send(from_phone, HERO_FALLBACK)
            req_counter.labels(outcome="budget_exhausted").inc()
            return

        hist = history.setdefault(from_phone, [])
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
                )
                limits.add_cost(cost)
                tok_counter.labels(kind="input").inc(tokens_in)
                tok_counter.labels(kind="output").inc(tokens_out)
                cost_counter.inc(cost)
                budget_gauge.set(limits.budget_remaining_usd())

        answer = "".join(parts).strip() or "(no response)"
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": answer})
        _trim_history(hist)
        _twilio_send(from_phone, answer)
        req_counter.labels(outcome="ok").inc()
        log.info(f"{channel} ok",
                 extra={"request_id": request_id, "ip": from_phone,
                        "outcome": "ok", "channel": channel,
                        "latency_ms": int((time.time() - start) * 1000),
                        "tokens_in": tokens_in, "tokens_out": tokens_out,
                        "cost_usd": round(cost, 6)})
    except Exception as e:
        req_counter.labels(outcome="error").inc()
        log.exception(f"{channel} failed",
                      extra={"request_id": request_id, "ip": from_phone,
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
    user_text = (form.get("Body") or "").strip()
    request_id = uuid.uuid4().hex[:12]

    if not from_phone or not user_text:
        return Response(status_code=200)

    user_text, _pan_redactions = redact_pan(user_text)
    if _pan_redactions:
        log.info(f"{endpoint_name} pan redacted",
                 extra={"request_id": request_id, "ip": from_phone,
                        "outcome": "pan_redacted", "channel": endpoint_name})

    if not limits.check_rate(from_phone):
        _twilio_send(from_phone, "Rate limit: 10 messages per minute. Try again shortly.")
        return Response(status_code=200)

    log.info(f"{endpoint_name} in",
             extra={"request_id": request_id, "ip": from_phone,
                    "outcome": f"{endpoint_name}_in",
                    "channel": endpoint_name,
                    "user_msg": user_text[:120]})

    background.add_task(_twilio_process, request_id, from_phone, user_text)
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
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
