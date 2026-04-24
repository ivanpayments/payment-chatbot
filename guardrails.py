"""Guardrails — post-process validator run BEFORE streaming the final
`done` SSE event. Extends `response_cleaner.py`.

Pattern P3/P4/P6 in the adversarial report: even after scratchpad scrubbing
and date-refusal, the LLM still (a) cites uncited "industry benchmark"
anchors, (b) quotes numeric claims that don't reconcile to the CSV, and
(c) leaks a handful of novel scratchpad phrasings the existing regex list
doesn't cover.

This module runs four rule classes in order over the assembled response:

    1. Extended forbidden-phrase filter (superset of response_cleaner's
       regexes — adds adversarial-report Appendix patterns).
    2. Numeric-claim verification against metrics_tool (deterministic CSV
       reads). Mismatch >5% → soft correction note appended. Mismatch
       >20% → number silently replaced with the CSV value.
    3. Citation stripping: sentences containing "industry benchmark",
       "typical merchant", "best-in-class", etc. without a source are
       swapped for a bracketed disclaimer.
    4. (Out-of-range date refusal stays in response_cleaner — this layer
       does not duplicate that rule but reads the same constants so the
       two files never drift.)

Design principles:
 - Pipeline of small functions; each takes text → text. Easy to add a
   new rule: append a line to ``_PIPELINE``.
 - Never raises — a failing check logs and returns the input unchanged.
 - Cross-checks call into ``metrics_tool`` (cached CSV), no new deps.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

from response_cleaner import clean_response

log = logging.getLogger("chatbot.guardrails")

# --- 1. Extended forbidden-phrase filter ------------------------------------
# Superset of response_cleaner._LEAK_SENTENCE_PATTERNS. The base cleaner
# already fires during streaming on sentence boundaries; these catch tail
# cases and any new phrasing flagged by the adversarial Appendix.

_EXTRA_LEAK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"my (prompt|instructions|system message)",
        r"i was (told|instructed) that",
        r"the (prompt|system prompt) (says|claims|states)",
        r"(looks like a different|a different) (file|dataset|schema)",
        r"^wait[,.\s]",
        r"^actually[,.\s]",
        r"^hmm[,.\s]",
        r"let me (recompute|double.check|verify|reconsider)",
        r"i apologi[sz]e for the (confusion|error|mistake)",
        r"i['’]ll (recompute|try again|rerun|redo)",
    )
]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _is_extra_leak(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return False
    return any(pat.search(s) for pat in _EXTRA_LEAK_PATTERNS)


def strip_extra_leaks(text: str) -> str:
    """Drop sentences matching any extended forbidden-phrase pattern.
    Preserves fenced code blocks untouched."""
    if not text:
        return text
    out_chunks: list[str] = []
    for block in re.split(r"(```[\s\S]*?```)", text):
        if block.startswith("```"):
            out_chunks.append(block)
            continue
        parts = _SENTENCE_SPLIT_RE.split(block)
        kept = [p for p in parts if not _is_extra_leak(p)]
        out_chunks.append(" ".join(kept))
    cleaned = "".join(out_chunks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


# --- 2. Numeric-claim verification ------------------------------------------
# Patterns we can cross-check via metrics_tool. Each entry: a compiled
# regex capturing the quoted number AND the metadata needed to call the
# tool, plus a function that returns the CSV ground truth.

# Example shapes we try to catch:
#   "Brazil soft-decline retry recovery rate of 75.1%"
#   "subscription-level recovery was 88%"
# We only verify shapes we're confident about — unrecognised numeric
# claims fall through unchallenged (better than false-positive rewrites).

_RETRY_CLAIM_RE = re.compile(
    r"(?P<country>brazil|india|mexico|germany|united kingdom|us|usa|united states|netherlands|france)"
    r"[^.\n]{0,120}?"
    r"(?P<kind>retry (?:recovery|approval|success)|soft.decline recovery|recovery rate)"
    r"[^.\n]{0,60}?"
    r"(?P<number>\d{1,3}(?:\.\d{1,2})?)\s?%",
    re.IGNORECASE,
)

_COUNTRY_TO_ISO2 = {
    "brazil": "BR", "india": "IN", "mexico": "MX", "germany": "DE",
    "united kingdom": "GB", "us": "US", "usa": "US",
    "united states": "US", "netherlands": "NL", "france": "FR",
}

SOFT_CORRECTION_THRESHOLD_PP = 5.0   # percentage points
HARD_REPLACE_THRESHOLD_PP = 20.0     # percentage points


def _csv_retry_rate_for(country_iso2: str, kind: str) -> tuple[float | None, str]:
    """Return (rate_pct, which_definition) for the country, or (None, '')
    on error. ``kind`` is the raw phrase from the claim; we pick the
    definition that best matches.
    """
    # Imported lazily so this module stays importable without pandas
    # if the CSV is not yet mounted (e.g. unit tests on CI).
    from metrics_tool import soft_decline_recovery_rate

    data = soft_decline_recovery_rate(country_iso2)
    if data.get("error"):
        return None, ""

    # "subscription-level" or "sub-level" → use sub rate.
    kl = (kind or "").lower()
    if "subscription" in kl or "sub-level" in kl or "sub level" in kl:
        rate = data.get("subscription_level_recovery_rate") or 0.0
        return rate * 100.0, "subscription_level"
    # Everything else (retry recovery/retry approval/retry success) → attempt.
    rate = data.get("attempt_level_retry_approval_rate") or 0.0
    return rate * 100.0, "attempt_level"


def verify_numeric_claims(text: str) -> str:
    """Cross-check recognisable retry-rate claims against metrics_tool.
    Appends a single bracketed note for soft mismatches; silently
    replaces the number for hard mismatches.

    Only verifies claims we can bind tightly to a country + metric. Other
    numbers pass through untouched — we'd rather under-correct than
    rewrite a correct figure.
    """
    if not text:
        return text

    # Work on a mutable copy; collect corrections to append at end.
    corrections: list[str] = []
    out = text

    for m in _RETRY_CLAIM_RE.finditer(text):
        country_word = m.group("country").lower()
        iso2 = _COUNTRY_TO_ISO2.get(country_word)
        if not iso2:
            continue
        try:
            claimed = float(m.group("number"))
        except ValueError:
            continue
        csv_pct, definition = _csv_retry_rate_for(iso2, m.group("kind"))
        if csv_pct is None:
            continue
        diff_pp = abs(claimed - csv_pct)
        if diff_pp >= HARD_REPLACE_THRESHOLD_PP:
            # Silently rewrite the number in-place.
            old_num = m.group("number")
            new_num = f"{csv_pct:.1f}"
            out = out.replace(f"{old_num}%", f"{new_num}%", 1)
            log.info("guardrails numeric rewrite: %s %s %s%% → %s%%",
                     iso2, definition, old_num, new_num)
        elif diff_pp >= SOFT_CORRECTION_THRESHOLD_PP:
            corrections.append(
                f"[NOTE: the live CSV shows {csv_pct:.2f}% "
                f"({definition.replace('_', '-')}) for {iso2}; the "
                f"quoted {claimed:.1f}% is slightly off]"
            )

    if corrections:
        # Deduplicate while preserving order.
        seen: set[str] = set()
        uniq = [c for c in corrections if not (c in seen or seen.add(c))]
        out = out.rstrip() + "\n\n" + "\n".join(uniq)

    return out


# --- 3. Citation stripping ---------------------------------------------------
# Any sentence citing an external anchor that isn't grounded in the CSV
# gets replaced with a disclaimer. Banned anchors come from adversarial
# report P6 (F11, F24). We're strict — better to under-cite than to
# mislead the Head of Payments on a benchmark that doesn't exist.

_UNCITED_ANCHOR_RE = re.compile(
    r"("
    # v1 banned anchors
    r"\bindustry benchmark[s]?\b|"
    r"\btypical merchant[s]?\b|"
    r"\bbest.in.class\b|"
    r"\bindustry average\b|"
    r"\b85.{0,3}88\s?%|"
    r"\$\s?2\s?B\s?ARR|"
    r"\$\s?2\s?billion\s?ARR|"
    r"\$\s?400M(?:\s?at\s?risk)?|"
    r"\$\s?30M\s?ARR|"
    # v2 new anchors (adversarial report P1-1)
    r"\btypical\s+(?:saas|merchant|e-?commerce|subscription)\s+(?:payment|approval|benchmark|profile|distribution|shape|pattern|concentration|approv\w+|recover\w+)?\b|"
    r"\btypical\s+global\s+saas\b|"
    # a bare ranged percentage not anchored to "our"/dataset (e.g. "84-91%",
    # "15-25%") — exempted below when a citation marker is present.
    r"(?<![\w])\d{1,2}\s?[\-–—]\s?\d{1,2}\s?%(?!\s*(?:below|above|gap|of\s+our|of\s+this\s+book))|"
    # "recoup/recover/claw back" + generic percentage (uncited)
    r"\b(?:recoup|recover|claw\s*back)\b[^.\n]{0,40}\b\d{1,2}\s?[\-–—]\s?\d{1,2}\s?%"
    r")",
    re.IGNORECASE,
)

# Unfilled template variables like "$X", "${amount}", "{3}" — if the model
# emits one, the answer is wrong (P1-1 follow-up). Replace with a
# placeholder that tells the user the math didn't land.
_TEMPLATE_VAR_RE = re.compile(r"\$[A-Z](?![A-Za-z])|\$\{[^}]+\}|\{\d+\}")
_TEMPLATE_PLACEHOLDER = "(value not computed)"

# A sentence is considered "cited" if it contains a URL, a markdown link,
# an explicit "Source:" / "According to" attribution, or a reference to a
# named published report. When any of these are present, external anchors
# are allowed through — the web_search tool surfaces URLs this way.
_CITATION_PRESENT_RE = re.compile(
    r"("
    r"https?://[^\s)\]]+|"              # bare URL
    r"\]\([^)]+\)|"                    # markdown link target
    r"\bsource\s*[:\-]|"                # "Source:" attribution
    r"\baccording to\b|"                # "According to X, ..."
    r"\bper (?:the|a|an)\b|"            # "per the 2024 report"
    r"\bas reported by\b|"              # "as reported by PYMNTS"
    r"\b(?:20\d{2})\s+(?:report|survey|study|index|whitepaper|analysis)\b"
    r")",
    re.IGNORECASE,
)

# Pure scale / dataset-size context that's always allowed — talks about
# our own book, not an external benchmark. Kept narrow so we don't
# accidentally wave through ARR fabrications.
_ALLOWED_SCALE_RE = re.compile(
    r"\b(100[kK]|100,000)\s+(?:row|attempt|billing|record)s?\b|"
    r"\b(?:our|the)\s+(?:dataset|book|sample)\b",
    re.IGNORECASE,
)

_CITATION_DISCLAIMER = (
    "[citation needed — this claim isn't grounded in the 100K-row dataset]"
)

# Sentences that are polite refusals or capability self-descriptions — these
# are NOT claims and must never be replaced with the disclaimer (adversarial
# report P0-4). If the anchor shows up inside a refusal/capability sentence,
# we leave the sentence alone.
_REFUSAL_CAPABILITY_RE = re.compile(
    r"(i['’]?m not able to|i (?:can['’]?t|cannot) (?:share|show|reveal|display|provide|disclose)|"
    r"those are confidential|confidential configuration|"
    r"here(?:['’]?s| is) what i can|i can help with|"
    r"what i['’]?m here to do|what i can tell you|"
    # v2 fix (validator, 2026-04-24): cover elided-apostrophe and full-verb
    # variants of the capability sentence. Both "here's" and "here is" must
    # carry the exemption.
    r"available via web_search|i['’]?ll run web_search)",
    re.IGNORECASE,
)


def _sentence_is_cited(sentence: str) -> bool:
    """True if the sentence carries a URL, markdown link, named-report
    reference, or explicit 'Source:' / 'According to' attribution."""
    return bool(_CITATION_PRESENT_RE.search(sentence or ""))


def _is_refusal_or_capability(sentence: str) -> bool:
    return bool(_REFUSAL_CAPABILITY_RE.search(sentence or ""))


def _is_structural_line(sentence: str) -> bool:
    """True if the sentence is a markdown bullet, heading, or table row —
    these are structure, not a claim, and should be exempt from the
    anchor strip (adversarial report P1-4)."""
    s = (sentence or "").lstrip()
    if not s:
        return False
    if s.startswith(("- ", "* ", "+ ")):
        return True
    if re.match(r"^\d+\.\s", s):
        return True
    if s.startswith("#"):
        return True
    if s.startswith("|") and s.rstrip().endswith("|"):
        return True
    return False


def _append_disclaimer(sentence: str) -> str:
    """Append the citation disclaimer as a suffix rather than replacing
    the sentence body. Idempotent — no-op if already appended."""
    s = (sentence or "").rstrip()
    if not s:
        return s
    if _CITATION_DISCLAIMER in s:
        return s
    return f"{s} {_CITATION_DISCLAIMER}"


def strip_template_variables(text: str) -> str:
    """Replace unfilled template vars (`$X`, `${amount}`, `{3}`) with a
    non-interpretive placeholder so the user doesn't see a literal `$X` in
    chat. Adversarial report P1-1 follow-up."""
    if not text:
        return text
    count = 0

    def _sub(_m: re.Match) -> str:
        nonlocal count
        count += 1
        return _TEMPLATE_PLACEHOLDER

    out = _TEMPLATE_VAR_RE.sub(_sub, text)
    if count:
        log.info("guardrails template-var rewrite: %d occurrence(s)", count)
    return out


def strip_uncited_anchors(text: str) -> str:
    """Append a citation disclaimer to any sentence containing a
    banned/uncited anchor, UNLESS:
      - the sentence carries a citation (URL, markdown link,
        Source:/According to, named report reference),
      - the sentence is a structural element (bullet, heading, table row),
      - the sentence is a polite refusal or capability self-description.

    Never replaces the whole sentence — the previous behaviour produced
    a bare `[citation needed ...]` bracket that looked like a backend
    error to the buyer (adversarial report P0-4, 2026-04-24). Operates
    sentence-by-sentence outside fenced code blocks so tables and pandas
    snippets are left alone.
    """
    if not text:
        return text
    out_chunks: list[str] = []
    for block in re.split(r"(```[\s\S]*?```)", text):
        if block.startswith("```"):
            out_chunks.append(block)
            continue
        # Preserve original newlines — splitting by newline first, then
        # sentence-splitting inside each line means we don't glue bullets
        # together into a single blob when rejoining.
        new_lines: list[str] = []
        for line in block.split("\n"):
            if not line.strip():
                new_lines.append(line)
                continue
            parts = _SENTENCE_SPLIT_RE.split(line)
            paragraph_cited = any(_sentence_is_cited(s or "") for s in parts)
            rebuilt: list[str] = []
            for p in parts:
                s = p or ""
                if not _UNCITED_ANCHOR_RE.search(s):
                    rebuilt.append(p)
                    continue
                # Exempt cases: dataset-scale references, structural
                # elements, refusals/capability, cited claims.
                if (_ALLOWED_SCALE_RE.search(s)
                        or _is_structural_line(s)
                        or _is_refusal_or_capability(s)
                        or _sentence_is_cited(s)
                        or paragraph_cited):
                    rebuilt.append(p)
                    continue
                # Suffix-append the disclaimer instead of replacing.
                rebuilt.append(_append_disclaimer(s))
            new_lines.append(" ".join(rebuilt))
        out_chunks.append("\n".join(new_lines))
    cleaned = "".join(out_chunks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


# --- 4. Pipeline composition -------------------------------------------------

# Each stage is (text, user_query) -> text. Keep stateless so callers can
# insert/remove/reorder stages without touching the rest.
PipelineStage = Callable[[str, str], str]


def _stage_clean(text: str, _user_query: str) -> str:
    return clean_response(text) if text else text


def _stage_extra_leaks(text: str, _user_query: str) -> str:
    return strip_extra_leaks(text) if text else text


def _stage_numeric(text: str, _user_query: str) -> str:
    try:
        return verify_numeric_claims(text) if text else text
    except Exception as e:  # noqa: BLE001 — guardrail must not raise
        log.warning("numeric verification stage failed: %s", e)
        return text


def _stage_citations(text: str, _user_query: str) -> str:
    try:
        return strip_uncited_anchors(text) if text else text
    except Exception as e:  # noqa: BLE001 — guardrail must not raise
        log.warning("citation stage failed: %s", e)
        return text


def _stage_templates(text: str, _user_query: str) -> str:
    try:
        return strip_template_variables(text) if text else text
    except Exception as e:  # noqa: BLE001 — guardrail must not raise
        log.warning("template-var stage failed: %s", e)
        return text


_DEFAULT_PIPELINE: list[PipelineStage] = [
    _stage_clean,
    _stage_extra_leaks,
    _stage_templates,
    _stage_numeric,
    _stage_citations,
]


def scrub_response(text: str, user_query: str,
                   pipeline: list[PipelineStage] | None = None) -> str:
    """Run the full guardrail pipeline on an assembled response.

    Called from ``app.py`` right before emitting the ``done`` SSE event.
    Idempotent — safe to re-run. If any stage raises, that stage is
    skipped and the input of that stage is passed forward unchanged.
    """
    if not text:
        return text
    stages = pipeline or _DEFAULT_PIPELINE
    out = text
    for stage in stages:
        try:
            new_out = stage(out, user_query)
            if isinstance(new_out, str):
                out = new_out
        except Exception as e:  # noqa: BLE001
            log.warning("guardrail stage %s failed: %s",
                        getattr(stage, "__name__", "?"), e)
    return out


__all__ = [
    "scrub_response",
    "strip_extra_leaks",
    "verify_numeric_claims",
    "strip_uncited_anchors",
    "strip_template_variables",
    "SOFT_CORRECTION_THRESHOLD_PP",
    "HARD_REPLACE_THRESHOLD_PP",
]
