"""Post-process filters for model responses and pre-process guards for user input.

Two jobs:

1. ``clean_response(text)`` — strips leaked internal-reasoning / scratch-pad
   phrases from streamed model output before it reaches the user. These are the
   "scratchpad leak" failures called out in the adversarial chatbot report
   (F3–F7): sentences like "The schema doesn't match..." or "Let me fix and
   rerun:" that expose self-correction to an executive user.

2. ``out_of_range_refusal(user_text)`` — returns a canned refusal string when
   the user asks about dates outside the CSV window (2023-01-01 → 2025-12-31)
   or asks for a forecast of a future period. Returns ``None`` if the query
   is in range.

3. ``trim_last_n_days(text, n)`` — best-effort guard: if the user asked for
   the last N days and the response's markdown table has N+1 rows, drop the
   earliest row. Runs last so the cleaner/refusal don't interact with it.

The module is deliberately small, dependency-free (stdlib regex only), and
unit-testable standalone.
"""
from __future__ import annotations

import re
from datetime import date

# Dataset bounds — must match the CSV actually deployed on the server.
DATA_START = date(2023, 1, 1)
DATA_END = date(2025, 12, 31)

# --- 1. Scratch-pad / reasoning leak filter ----------------------------------

# Phrases or sentence starters that should never appear in the user-facing
# response. Each entry is a regex matched against a whole sentence (case-
# insensitive). If a sentence matches, the whole sentence is removed.
_LEAK_SENTENCE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"the schema doesn['’]?t match",
        r"the csv schema doesn['’]?t match",
        r"the data schema doesn['’]?t match",
        r"the described schema",
        r"the months look off",
        r"the processor column has no\s+`?psp_`?\s+prefix",
        r"this looks like a different file",
        r"let me (fix|check|confirm|rerun|re-run|first|try|look)[^.]*(and rerun|and re-run)?",
        r"^looking at the (data|csv|file)",
        r"^good\s*[—-]\s*i now have",
        r"i now have everything i need",
        r"the dataset['’]?s date range is 2025",
    )
]

# Inline artefacts like "(thinking: ...)" or "(scratch: ...)" — removed
# wherever they appear within a sentence.
_INLINE_ARTEFACT_RE = re.compile(
    r"\(\s*(?:thinking|scratch|scratchpad|note to self)\s*:\s*[^)]*\)",
    re.IGNORECASE,
)

# Sentence splitter — cheap, good enough for markdown prose. Splits on
# ".!? " keeping the terminator, and also splits on newlines so a leak in
# a bullet or heading can be removed cleanly.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _is_leak(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return False
    for pat in _LEAK_SENTENCE_PATTERNS:
        if pat.search(s):
            return True
    return False


def clean_response(text: str) -> str:
    """Remove scratchpad-leak sentences and inline (thinking: ...) artefacts.

    Preserves markdown tables, code fences, and bullet structure — splits only
    outside fenced code blocks to avoid mangling pandas output.
    """
    if not text:
        return text

    # Strip inline artefacts first, globally.
    text = _INLINE_ARTEFACT_RE.sub("", text)

    # Skip scrubbing inside fenced code blocks. Walk block-by-block.
    out_chunks: list[str] = []
    in_code = False
    for block in re.split(r"(```[\s\S]*?```)", text):
        if block.startswith("```"):
            out_chunks.append(block)
            continue
        # Non-code block — split into sentences/lines, drop leaky ones.
        parts = _SENTENCE_SPLIT_RE.split(block)
        kept: list[str] = [p for p in parts if not _is_leak(p)]
        # Rejoin with a single space — the original spacing is lost, but the
        # model outputs markdown where that's fine.
        out_chunks.append(" ".join(kept))

    cleaned = "".join(out_chunks)
    # Collapse runs of 3+ newlines left by removed sentences into a max of 2.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Collapse double spaces that the rejoin can create.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


# --- 2. Out-of-range / future-forecast refusal -------------------------------

REFUSAL_TEXT = (
    "This query falls outside the dataset's date range "
    "(2023-01-01 to 2025-12-31). I can answer questions about data within "
    "that window."
)

# Month names — full and 3-letter. Ordered so regex prefers longer match.
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Matches things like: "June 2027", "Jan 2022", "March 2026", "2026-04"
_MONTH_YEAR_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS.keys(), key=len, reverse=True)) +
    r")\s+(\d{4})\b",
    re.IGNORECASE,
)
# Matches bare ISO-ish "YYYY-MM" or "YYYY" in-year references.
_ISO_YM_RE = re.compile(r"\b(\d{4})-(\d{1,2})(?:-(\d{1,2}))?\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Phrases that clearly ask for a forecast.
_FORECAST_RE = re.compile(
    r"\b(forecast|project|predict|projected|extrapolat\w*|"
    r"what will (the )?(approval|decline|rate|volume)|"
    r"next (month|quarter|year)|"
    r"in (the )?(next|coming) (\d+\s+)?(month|quarter|year)s?)\b",
    re.IGNORECASE,
)


def _is_out_of_range_ym(year: int, month: int | None = None) -> bool:
    if year < DATA_START.year or year > DATA_END.year:
        return True
    if month is None:
        return False
    if year == DATA_START.year and month < DATA_START.month:
        return True
    if year == DATA_END.year and month > DATA_END.month:
        return True
    return False


def out_of_range_refusal(user_text: str) -> str | None:
    """Return the refusal string if the user asks about a date outside the
    CSV window or asks for a forecast of a future period. Return ``None`` if
    the query is in range (or contains no explicit date at all — in that case
    the LLM handles it normally)."""
    if not user_text:
        return None
    text = user_text.strip()

    # Scan for "Month YYYY" references. If ANY such reference is out of range
    # (or any "YYYY-MM" / bare "YYYY"), refuse — safer to false-positive on a
    # speculative forecast than to ship a fabricated answer.
    found_any_date = False
    for m in _MONTH_YEAR_RE.finditer(text):
        found_any_date = True
        month = _MONTHS[m.group(1).lower()]
        year = int(m.group(2))
        if _is_out_of_range_ym(year, month):
            return REFUSAL_TEXT

    for m in _ISO_YM_RE.finditer(text):
        found_any_date = True
        year = int(m.group(1))
        month = int(m.group(2)) if m.group(2) else None
        if month and 1 <= month <= 12:
            if _is_out_of_range_ym(year, month):
                return REFUSAL_TEXT
        else:
            if _is_out_of_range_ym(year):
                return REFUSAL_TEXT

    # Bare YYYY years (only trigger if no other date pattern already did).
    if not found_any_date:
        for m in _YEAR_RE.finditer(text):
            year = int(m.group(1))
            if _is_out_of_range_ym(year):
                return REFUSAL_TEXT

    # Forecast phrasing — only refuse when it also mentions an explicit
    # future trigger, otherwise "predict decline" is a valid model question.
    if _FORECAST_RE.search(text):
        # Only refuse if paired with a future year or a "next {period}" phrase.
        if re.search(
            r"\bnext\s+(\d+\s+)?(month|quarter|year)s?\b",
            text, re.IGNORECASE,
        ):
            return REFUSAL_TEXT
        for m in _YEAR_RE.finditer(text):
            if int(m.group(1)) > DATA_END.year:
                return REFUSAL_TEXT

    return None


# --- 3. last-N-days off-by-one guard ----------------------------------------

_LAST_N_DAYS_RE = re.compile(r"\blast\s+(\d+)\s+days?\b", re.IGNORECASE)


def user_requested_last_n_days(user_text: str) -> int | None:
    """Parse 'last N days' out of user text. Returns N or None."""
    if not user_text:
        return None
    m = _LAST_N_DAYS_RE.search(user_text)
    return int(m.group(1)) if m else None


def trim_last_n_days(text: str, n: int) -> str:
    """If the response contains a markdown table whose first column holds date
    strings and the row count exceeds ``n``, drop the earliest-dated rows so
    exactly ``n`` date rows remain. No-op if the shape doesn't match.

    A date cell matches ``YYYY-MM-DD`` (ISO) or ``YYYY-MM-DDTHH:MM...``. The
    table must have a header row + separator row + data rows.
    """
    if not text or n <= 0:
        return text

    lines = text.splitlines()
    # Walk lines looking for a markdown table. Process the first one that has
    # date-like rows; tables further down are left alone.
    i = 0
    out_lines: list[str] = []
    patched = False
    while i < len(lines):
        line = lines[i]
        if (not patched and line.lstrip().startswith("|")
                and i + 1 < len(lines)
                and re.match(r"^\s*\|\s*[:\- ]+\|", lines[i + 1])):
            # Collect the table rows.
            header = line
            sep = lines[i + 1]
            j = i + 2
            rows: list[str] = []
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(lines[j])
                j += 1

            # Extract the first-column cell of each row.
            def _first_cell(row: str) -> str:
                parts = row.split("|")
                return parts[1].strip() if len(parts) >= 2 else ""

            date_rows = [
                (r, _first_cell(r))
                for r in rows
            ]
            date_rows_with_date = [
                (r, c) for (r, c) in date_rows
                if re.match(r"^\d{4}-\d{2}-\d{2}", c)
            ]

            if date_rows_with_date and len(date_rows_with_date) > n:
                # Sort by the date cell ascending, keep the N most-recent.
                date_rows_with_date.sort(key=lambda rc: rc[1])
                drop_count = len(date_rows_with_date) - n
                dropped_rows = {id(r) for (r, _) in date_rows_with_date[:drop_count]}
                kept_rows = [r for r in rows if id(r) not in dropped_rows]
                out_lines.append(header)
                out_lines.append(sep)
                out_lines.extend(kept_rows)
                patched = True
                i = j
                continue

        out_lines.append(line)
        i += 1

    return "\n".join(out_lines)


__all__ = [
    "clean_response",
    "out_of_range_refusal",
    "user_requested_last_n_days",
    "trim_last_n_days",
    "REFUSAL_TEXT",
    "DATA_START",
    "DATA_END",
]
