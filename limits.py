"""Rate limits, daily budget, and session caps for the chatbot."""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

# Per-IP sliding window
RATE_WINDOW_SEC = 60
RATE_LIMIT = 10

# Daily spend cap (USD)
DAILY_BUDGET_USD = 5.00

# 10 user turns + 10 assistant turns
SESSION_MSG_CAP = 20

# Per-model pricing (USD per million tokens). Source: Anthropic public
# list as of 2026-04. Cache write ≈ 1.25x input; cache read ≈ 0.1x input.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "haiku":  {"input": 1.0,  "output": 5.0,  "cache_write": 1.25,  "cache_read": 0.10},
    "sonnet": {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
    "opus":   {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
}

# Backward-compatible default (sonnet). Older callers that don't pass a
# tier fall back to Sonnet pricing so the budget accountant never crashes.
_DEFAULT_TIER = "sonnet"

# Legacy constants retained for any external importer — point at Sonnet
# so existing readings stay in the right order of magnitude.
PRICE_INPUT_PER_MTOK = MODEL_PRICING[_DEFAULT_TIER]["input"]
PRICE_OUTPUT_PER_MTOK = MODEL_PRICING[_DEFAULT_TIER]["output"]
PRICE_CACHE_WRITE_PER_MTOK = MODEL_PRICING[_DEFAULT_TIER]["cache_write"]
PRICE_CACHE_READ_PER_MTOK = MODEL_PRICING[_DEFAULT_TIER]["cache_read"]

BUDGET_PATH = Path("/opt/chatbot/data/budget.json")


# Anthropic web_search pricing: $10 per 1,000 searches = $0.01 per search.
# Source: platform.claude.com/docs/.../tool-use/web-search-tool (2026-04).
WEB_SEARCH_PRICE_PER_REQUEST_USD = 0.01


def estimate_cost_usd(input_tokens: int, output_tokens: int,
                      cache_read: int = 0, cache_write: int = 0,
                      tier: str = _DEFAULT_TIER,
                      web_search_requests: int = 0) -> float:
    """Estimate USD cost for a single turn. ``tier`` is one of
    ``'haiku' | 'sonnet' | 'opus'``; unknown tiers fall back to Sonnet
    pricing so total-spend tracking stays conservative and never crashes
    on a tier we haven't priced yet.

    ``web_search_requests`` is the count Anthropic reports in
    ``usage.server_tool_use.web_search_requests`` — billed at
    $0.01/request on top of token cost.
    """
    prices = MODEL_PRICING.get((tier or "").lower(), MODEL_PRICING[_DEFAULT_TIER])
    token_cost = (
        input_tokens * prices["input"]
        + output_tokens * prices["output"]
        + cache_read * prices["cache_read"]
        + cache_write * prices["cache_write"]
    ) / 1_000_000
    return token_cost + (web_search_requests * WEB_SEARCH_PRICE_PER_REQUEST_USD)


class Limits:
    def __init__(self, budget_path: Path = BUDGET_PATH) -> None:
        self._ip_windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()
        self._budget_path = budget_path

    def check_rate(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            dq = self._ip_windows[ip]
            while dq and dq[0] < now - RATE_WINDOW_SEC:
                dq.popleft()
            if len(dq) >= RATE_LIMIT:
                return False
            dq.append(now)
        return True

    @staticmethod
    def _today_key() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load(self) -> dict:
        if self._budget_path.exists():
            try:
                return json.loads(self._budget_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self, d: dict) -> None:
        self._budget_path.parent.mkdir(parents=True, exist_ok=True)
        self._budget_path.write_text(json.dumps(d))

    def spent_today_usd(self) -> float:
        with self._lock:
            return self._load().get(self._today_key(), 0.0)

    def budget_remaining_usd(self) -> float:
        return max(0.0, DAILY_BUDGET_USD - self.spent_today_usd())

    def budget_exhausted(self) -> bool:
        return self.spent_today_usd() >= DAILY_BUDGET_USD

    def add_cost(self, cost_usd: float) -> None:
        with self._lock:
            d = self._load()
            k = self._today_key()
            d[k] = round(d.get(k, 0.0) + cost_usd, 6)
            self._save(d)

    @staticmethod
    def session_over_cap(history: list) -> bool:
        return len(history) >= SESSION_MSG_CAP
