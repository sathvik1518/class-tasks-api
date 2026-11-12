"""The rules for a title. One place, so the API, the service and the tests all agree."""
from __future__ import annotations

import unicodedata

from app.domain.errors import InvalidTitle


def normalize_title(raw: str) -> str:
    """Same text in one canonical shape: composed accents (NFC), no outer spaces, runs of white space become one space."""
    return " ".join(unicodedata.normalize("NFC", raw).split())


def title_key(title: str) -> str:
    """What 'the same title' means: ignoring upper/lower case. `Homework` and `HOMEWORK` are one title."""
    return title.casefold()


def _visible(ch: str) -> bool:
    return not ch.isspace() and unicodedata.category(ch) != "Cf"  # Cf = invisible format marks such as the zero-width space


def check_title(raw: object, max_length: int) -> str:
    """Return the cleaned title or raise InvalidTitle. `max_length` comes from the settings."""
    if not isinstance(raw, str):
        raise InvalidTitle("Title must be text.")
    title = normalize_title(raw)
    if any(unicodedata.category(ch) == "Cc" for ch in title):
        raise InvalidTitle("Title can't contain control characters.")
    if not any(_visible(ch) for ch in title):
        raise InvalidTitle("Title can't be empty.")
    if len(title) > max_length:
        raise InvalidTitle(f"Title can be at most {max_length} characters (this one is {len(title)}).")
    return title
