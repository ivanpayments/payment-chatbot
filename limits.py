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

# Claude Opus 4.6 pricing (USD per million tokens)
PRICE_INPUT_PER_MTOK = 5.0
PRICE_OUTPUT_PER_MTOK = 25.0
PRICE_CACHE_WRITE_PER_MTOK = 6.25
PRICE_CACHE_READ_PER_MTOK = 0.50

BUDGET_PATH = Path("/opt/chatbot/data/budget.json")


def estimate_cost_usd(input_tokens: int, output_tokens: int,
                      cache_read: int = 0, cache_write: int = 0) -> float:
    return (
        input_tokens * PRICE_INPUT_PER_MTOK
        + output_tokens * PRICE_OUTPUT_PER_MTOK
        + cache_read * PRICE_CACHE_READ_PER_MTOK
        + cache_write * PRICE_CACHE_WRITE_PER_MTOK
    ) / 1_000_000


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
            except Exception:
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
