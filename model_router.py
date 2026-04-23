"""Hybrid Haiku/Sonnet/Opus model router.

Pattern P11 in the adversarial plan — `model_architecture_evaluation.md`
recommends routing: Haiku for simple lookups, Opus for multi-hop /
counterfactual / forecast / ambiguous, Sonnet as the default safety net.

Classifier is rule-based (regex) for speed and determinism — an LLM
classifier adds ~500ms and ~$0.001/query without outperforming a tuned
regex on a bounded question surface.

Public API:

    classify_query(user_text) -> ("haiku" | "sonnet" | "opus")
    model_id_for(tier) -> str          # maps tier to Anthropic model ID
    resolve_model(user_text) -> (tier, model_id, label)

Env override: ``FORCE_MODEL=haiku|sonnet|opus`` short-circuits the
classifier. Useful for testing a specific path end-to-end without
crafting a matching query.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("chatbot.router")

# --- Model IDs ---------------------------------------------------------------
# These match Anthropic's published model names as of 2026-04 and the
# pricing table in limits.py. If they change, update both files.

MODEL_HAIKU = os.getenv("CHATBOT_MODEL_HAIKU", "claude-haiku-4-5-20251001")
MODEL_SONNET = os.getenv("CHATBOT_MODEL_SONNET", "claude-sonnet-4-6")
MODEL_OPUS = os.getenv("CHATBOT_MODEL_OPUS", "claude-opus-4-7")

# Human-readable labels streamed to the UI badge.
MODEL_LABELS = {
    "haiku": "Haiku",
    "sonnet": "Sonnet",
    "opus": "Opus",
}


# --- Classifier rules --------------------------------------------------------

# "Hard" triggers: send to Opus. Multi-hop reasoning, counterfactuals,
# forecasts, ambiguous judgments, anything likely to need chained
# code_execution + metrics_tool calls.
_HARD_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bwhy\b",
        r"\bif (we|i|you|they) (fixed|fix|could|would|raised|dropped|changed)\b",
        r"\bwhat if\b",
        r"\bhow much would (we|i|you) save\b",
        r"\bcounterfactual\b",
        r"\bpredict(ion|ed)?\b",
        r"\bforecast(s|ing)?\b",
        r"\bextrapolat\w+\b",
        r"\bproject(?!ed\s+history)\w*\b",  # "project" / "projecting"; not "projected history"
        r"\b(retry success|retry recovery|recovery rate|recover)\b",
        r"\bby\s+\w+\s+by\s+\w+\b",          # two-dimensional breakdown
        r"\bis\b.{0,40}\b(good|bad|a problem|concerning|healthy|below par|above par)\b",
        r"\bshould (i|we) (be worried|act|fix|prioritise|prioritize)\b",
        r"\blast\s+\d+\s+(day|week|month)s?\b",
        r"\b(compare|comparison|vs\.?|versus)\b",
    )
]

# "Simple" triggers: send to Haiku. Lookups, direct metric retrieval,
# single-dimension enumerations.
_SIMPLE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^\s*what(?:['’]s| is| are)\s+(my|our|the)\s+",
        r"^\s*show\s+(me\s+)?",
        r"^\s*how\s+much\s+(is|was|did|does)\b",
        r"^\s*how many\b",
        r"^\s*list\s+",
        r"^\s*give\s+me\s+",
        r"^\s*tell\s+me\s+",
        r"\bapproval rate for\b",
        r"\btotal (attempts|volume|amount)\b",
        r"\b(rank|league table|breakdown)\b(?!.*\bby\s+\w+\s+by\b)",
    )
]


def _has_any(text: str, patterns) -> bool:
    return any(p.search(text) for p in patterns)


def classify_query(user_text: str) -> str:
    """Return one of ``'haiku'``, ``'sonnet'``, ``'opus'``.

    Priority:
        1. ``FORCE_MODEL`` env var (any non-empty value of haiku/sonnet/opus).
        2. Hard triggers → ``opus``.
        3. Simple triggers → ``haiku``.
        4. Default → ``sonnet``.
    """
    override = os.getenv("FORCE_MODEL", "").strip().lower()
    if override in ("haiku", "sonnet", "opus"):
        return override

    if not user_text:
        return "sonnet"
    text = user_text.strip()

    # Hard wins ties — if a query has BOTH "what's my retry recovery"
    # and "what's my total volume", we'd rather send it to Opus than
    # mis-route to Haiku. Cheaper to over-spend than to fabricate.
    if _has_any(text, _HARD_PATTERNS):
        return "opus"
    if _has_any(text, _SIMPLE_PATTERNS):
        return "haiku"
    return "sonnet"


def model_id_for(tier: str) -> str:
    tier = (tier or "").lower()
    if tier == "haiku":
        return MODEL_HAIKU
    if tier == "opus":
        return MODEL_OPUS
    return MODEL_SONNET


def resolve_model(user_text: str) -> tuple[str, str, str]:
    """Classify and return ``(tier, model_id, label)``.

    ``label`` is the human-readable name the UI renders in the model
    badge (``Haiku`` / ``Sonnet`` / ``Opus``).
    """
    tier = classify_query(user_text)
    return tier, model_id_for(tier), MODEL_LABELS[tier]


# Preamble line emitted as a text chunk when Opus is used, so users
# aren't puzzled by the longer latency. Plain-spoken, no hype.
OPUS_PREAMBLE = (
    "I'm using the deep research model for this — expect a slightly "
    "longer response time.\n\n"
)


__all__ = [
    "classify_query",
    "resolve_model",
    "model_id_for",
    "MODEL_HAIKU",
    "MODEL_SONNET",
    "MODEL_OPUS",
    "MODEL_LABELS",
    "OPUS_PREAMBLE",
]
