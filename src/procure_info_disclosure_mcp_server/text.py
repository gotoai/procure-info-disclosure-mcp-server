"""Turning what the portal returns into values a model can use."""

from __future__ import annotations

import html
import re
import unicodedata

_ERA_BASE = {"令和": 2018, "平成": 1988, "昭和": 1925}
_WAREKI = re.compile(r"(令和|平成|昭和)\s*(\d{1,2})年\s*(\d{1,2})月\s*(\d{1,2})日")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_BR = re.compile(r"<\s*br\s*/?>", re.IGNORECASE)
_BLOCK_END = re.compile(r"<\s*/(?:p|div|li|tr)\s*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n\s*\n\s*\n+")


def wareki_to_iso(text: str | None) -> str | None:
    """「令和03年11月24日」 -> "2021-11-24". None when no Japanese-era date is present."""
    if not text:
        return None
    match = _WAREKI.search(unicodedata.normalize("NFKC", text))
    if not match:
        return None
    era, year, month, day = match.groups()
    return f"{_ERA_BASE[era] + int(year):04d}-{int(month):02d}-{int(day):02d}"


def iso_to_portal_date(value: str) -> str:
    """"2026-10-01" -> "2026/10/01", the form the portal's date fields take."""
    match = _ISO_DATE.match(value.strip())
    if not match:
        raise ValueError(f"{value!r} is not a date in YYYY-MM-DD form.")
    return "/".join(match.groups())


def html_to_text(markup: str | None) -> str:
    """A notice body arrives as HTML with <br> line breaks; keep the lines, drop the tags."""
    if not markup:
        return ""
    text = _BR.sub("\n", markup)
    text = _BLOCK_END.sub("\n", text)
    text = html.unescape(_ANY_TAG.sub("", text))
    lines = [line.rstrip() for line in text.splitlines()]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip("\n")


def clean_text(markup: str | None) -> str:
    """A single value cell: tags and entities removed, whitespace collapsed."""
    if not markup:
        return ""
    text = html.unescape(_ANY_TAG.sub(" ", markup))
    return re.sub(r"\s+", " ", text).strip()


def normalize_for_match(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()
