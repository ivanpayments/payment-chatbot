"""Parse page_text.docx and regenerate static/content.json.

Docx is the single source of truth. Each section is a `Heading 1` like [HERO],
[SECTION - WHAT THIS IS], etc. Within a section, fixed "label" paragraphs
(e.g. "Uptitle (top small line, all caps)", "Heading", "Body") are followed by
one or more value paragraphs until the next label or section.

Run after editing page_text.docx:
    python "Claude files/sync_docx.py"
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parent.parent
# Canonical combined docx lives one level above, shared with the routing-simulator page.
DOCX = ROOT.parent / "page_text.docx"
CONTENT = ROOT / "static" / "content.json"

CHATBOT_START = "Chatbot landing-page copy"
PORTFOLIO_START_MARKER = "Portfolio landing page copy"


def _norm(s: str) -> str:
    return (s or "").strip()


def _is_section_heading(p) -> bool:
    return p.style.name == "Heading 1" and _norm(p.text).startswith("[")


def _section_key(p) -> str:
    return _norm(p.text).strip("[]").strip().upper()


def load_chatbot_sections():
    """Return {section_key: [paragraphs]} for the chatbot half of the docx."""
    doc = Document(str(DOCX))
    sections: dict[str, list] = {}
    current = None
    in_portfolio = False

    for p in doc.paragraphs:
        text = _norm(p.text)
        if PORTFOLIO_START_MARKER in text:
            in_portfolio = True
            continue
        if in_portfolio:
            continue
        if _is_section_heading(p):
            current = _section_key(p)
            sections[current] = []
            continue
        if current is None:
            continue
        sections[current].append(p)
    return sections


def _values_by_label(paragraphs, labels):
    """Walk paragraphs, splitting into buckets keyed by each label.

    `labels` is a list of (label_text, key). A paragraph whose text starts with
    one of the label_text entries becomes a bucket boundary. All following
    non-empty paragraphs up to the next label go into that bucket as a list.
    """
    label_map = {l.lower(): k for l, k in labels}
    current_key = None
    buckets: dict[str, list] = {k: [] for _, k in labels}

    for p in paragraphs:
        text = _norm(p.text)
        if not text:
            continue
        matched = None
        low = text.lower()
        for label_text, key in labels:
            if low.startswith(label_text.lower()):
                matched = key
                break
        if matched:
            current_key = matched
            continue
        if current_key:
            buckets[current_key].append(p)
    return buckets


def first_text(paragraphs):
    return _norm(paragraphs[0].text) if paragraphs else ""


def all_text(paragraphs):
    return [_norm(p.text) for p in paragraphs if _norm(p.text)]


def bold_opener(text):
    """Wrap the opening phrase (up to first '. ') in <b>...</b>."""
    if not text:
        return text
    idx = text.find(". ")
    if idx == -1:
        return text
    return f"<b>{text[:idx + 1]}</b>{text[idx + 1:]}"


def bold_first_sentence(text):
    """Same as bold_opener — named for the synthetic note case."""
    return bold_opener(text)


def build_content(sections):
    # [HERO]
    hero = _values_by_label(sections.get("HERO", []), [
        ("Uptitle", "uptitle"),
        ("H1", "h1"),
        ("Subtitle", "sub"),
        ("Stats", "stats"),
    ])
    hero_stats = []
    for line in all_text(hero["stats"]):
        if "|" in line:
            k, v = [p.strip() for p in line.split("|", 1)]
            hero_stats.append({"k": k, "v": v})

    # [SECTION - WHAT THIS IS]
    what_key = next(k for k in sections if k.startswith("SECTION") and "WHAT" in k)
    what = _values_by_label(sections[what_key], [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Body", "body"),
    ])

    # [SECTION - TRANSACTIONS]
    tx_key = next(k for k in sections if k.startswith("SECTION") and "TRANSACTIONS" in k)
    tx_paras = sections[tx_key]
    tx = _values_by_label(tx_paras, [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Stats", "stats"),
        ("Body paragraph 1", "body1"),
        ("Body paragraph 2", "body2"),
        ("Note", "note"),
    ])

    stats = []
    for line in all_text(tx["stats"]):
        if "|" not in line:
            continue
        k, v = [part.strip() for part in line.split("|", 1)]
        stats.append({"k": k, "v": v})

    # body paragraph 1 is: one intro line (Normal) + bulleted list (List Paragraph).
    # We need to walk the underlying paragraphs and separate by style.
    body1_intro_parts = []
    body1_bullets = []
    for p in tx["body1"]:
        text = _norm(p.text)
        if not text:
            continue
        if p.style.name == "List Paragraph":
            body1_bullets.append(text)
        else:
            body1_intro_parts.append(text)
    body1_intro = " ".join(body1_intro_parts)

    body_after_stats_html = html.escape(body1_intro)
    if body1_bullets:
        body_after_stats_html = (
            f"<p style='margin:0 0 10px'>{html.escape(body1_intro)}</p>"
            "<ul style='margin:0; padding-left:20px'>"
            + "".join(f"<li>{html.escape(b)}</li>" for b in body1_bullets)
            + "</ul>"
        )

    body2_text = " ".join(all_text(tx["body2"]))
    body_synthetic_html = bold_first_sentence(body2_text)

    # [SECTION - WHO IT IS FOR]
    who_key = next(k for k in sections if k.startswith("SECTION") and "WHO" in k)
    who = _values_by_label(sections[who_key], [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Body", "body"),
    ])

    # [SECTION - WHY IT EXISTS] — prefer the one with Points; "WHY THIS MATTERS" is a separate concern
    why_candidates = [k for k in sections if k.startswith("SECTION") and "WHY IT EXISTS" in k]
    why_key = why_candidates[0] if why_candidates else next(
        (k for k in sections if k.startswith("SECTION") and "WHY" in k and "MATTERS" not in k), None
    )
    why_paras = sections.get(why_key, []) if why_key else []
    why = _values_by_label(why_paras, [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Body", "body_intro"),
        ("Points", "points"),
    ])
    points = [bold_opener(t) for t in all_text(why["points"])]

    # [SECTION - WHY THIS MATTERS] — distinct from WHY IT EXISTS
    whymatters_key = next((k for k in sections if k.startswith("SECTION") and "WHY THIS MATTERS" in k), None)
    whymatters = _values_by_label(sections.get(whymatters_key, []), [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Body", "body"),
        ("Stats", "stats"),
    ]) if whymatters_key else None
    whymatters_stats = []
    if whymatters:
        for line in all_text(whymatters["stats"]):
            if "|" in line:
                k, v = [p.strip() for p in line.split("|", 1)]
                whymatters_stats.append({"k": k, "v": v})

    # [SECTION - HOW IT IS BUILT]
    howbuilt_key = next((k for k in sections if k.startswith("SECTION") and "HOW IT IS BUILT" in k), None)
    howbuilt = _values_by_label(sections.get(howbuilt_key, []), [
        ("Label", "label"),
        ("Heading", "heading"),
        ("Body", "body"),
    ]) if howbuilt_key else None

    # [CALL TO ACTION]
    cta = _values_by_label(sections.get("CALL TO ACTION", []), [
        ("Button text", "text"),
    ])

    # [CHAT PANEL]
    chat_panel = _values_by_label(sections.get("CHAT PANEL", []), [
        ("Title", "title"),
        ("Subtitle", "sub"),
        ("Chips label", "chips_label"),
    ])

    # [SUGGESTED QUESTIONS]
    sq = sections.get("SUGGESTED QUESTIONS", [])
    chip_lines = []
    for p in sq:
        text = _norm(p.text)
        if not text or text.lower().startswith("one per line"):
            continue
        if "|" not in text:
            continue
        chip_lines.append(text)
    chips = []
    for line in chip_lines:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        stakeholder, question = parts[0], parts[1]
        chip = {"stakeholder": stakeholder, "question": question}
        if len(parts) >= 3 and parts[2].lower() == "prebuilt":
            chip["prebuilt"] = True
        chips.append(chip)

    # [CHAT UI LABELS]
    ui = _values_by_label(sections.get("CHAT UI LABELS", []), [
        ("Input placeholder", "placeholder"),
        ("Send button", "send_label"),
        ('"You" label', "you_label"),
        ('"Claude" label', "claude_label"),
        ("Thinking label", "thinking_label"),
    ])

    data = {
        "hero": {
            "uptitle": first_text(hero["uptitle"]),
            "h1": first_text(hero["h1"]),
            "sub": first_text(hero["sub"]),
            "stats": hero_stats if hero_stats else None,
        },
        "section_what": {
            "label": first_text(what["label"]),
            "heading": first_text(what["heading"]),
            "body": " ".join(all_text(what["body"])),
        },
        "section_book": {
            "label": first_text(tx["label"]),
            "heading": first_text(tx["heading"]),
            **({"stats": stats} if stats else {}),
            "body_after_stats": body_after_stats_html,
            "body_synthetic": body_synthetic_html,
        },
        "section_who": {
            "label": first_text(who["label"]),
            "heading": first_text(who["heading"]),
            "body": " ".join(all_text(who["body"])),
        },
        "section_why": {
            "label": first_text(why["label"]),
            "heading": first_text(why["heading"]),
            "body": " ".join(all_text(why["body_intro"])),
            "points": points,
        },
        **({"section_whymatters": {
            "label": first_text(whymatters["label"]),
            "heading": first_text(whymatters["heading"]),
            "body": " ".join(all_text(whymatters["body"])),
            "stats": whymatters_stats if whymatters_stats else None,
        }} if whymatters else {}),
        **({"section_howbuilt": {
            "label": first_text(howbuilt["label"]),
            "heading": first_text(howbuilt["heading"]),
            "body": " ".join(all_text(howbuilt["body"])),
        }} if howbuilt else {}),
        "cta": {
            "text": first_text(cta["text"]) or "Give it a try",
            "arrow": "\u2192",
        },
        "chat": {
            "status_pill": "\u25cf Live",
            "title": first_text(chat_panel["title"]),
            "sub": first_text(chat_panel["sub"]),
            "chips_label": first_text(chat_panel["chips_label"]),
            "chips": chips,
            "placeholder": first_text(ui["placeholder"]),
            "send_label": first_text(ui["send_label"]),
            "you_label": first_text(ui["you_label"]),
            "claude_label": first_text(ui["claude_label"]),
            "thinking_label": first_text(ui["thinking_label"]),
        },
    }
    return data


def main():
    sections = load_chatbot_sections()
    data = build_content(sections)
    CONTENT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"content.json saved: {CONTENT}")
    print(f"  hero.h1           = {data['hero']['h1']!r}")
    print(f"  section_why.points= {len(data['section_why']['points'])} bullets")
    print(f"  chat.chips        = {len(data['chat']['chips'])} chips")


if __name__ == "__main__":
    main()
