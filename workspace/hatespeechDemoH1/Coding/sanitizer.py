"""Deterministic normalization for untrusted social-media text."""

from __future__ import annotations

import html
import re
import unicodedata

from .schemas import TwitterCommentInput

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DANGEROUS_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object)\b[^>]*>.*?<\s*/\s*\1\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]{0,1000}>")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{1,15}\b")
_SPACE_RE = re.compile(r"\s+")


def sanitize_text(value: str) -> str:
    """Strip executable markup and normalize URLs, handles, Unicode, and spacing."""

    if not isinstance(value, str):
        raise TypeError("comment text must be a string")
    normalized = html.unescape(unicodedata.normalize("NFKC", value))
    normalized = _CONTROL_RE.sub("", normalized)
    normalized = _DANGEROUS_BLOCK_RE.sub(" ", normalized)
    normalized = _TAG_RE.sub(" ", normalized)
    normalized = _URL_RE.sub("[URL]", normalized)
    normalized = _HANDLE_RE.sub("[USER]", normalized)
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    if not normalized:
        raise ValueError("comment text is empty after sanitization")
    return normalized


class InputSanitizer:
    """Sanitize a validated comment while preserving safe metadata."""

    def sanitize(self, comment: TwitterCommentInput) -> TwitterCommentInput:
        if not isinstance(comment, TwitterCommentInput):
            raise TypeError("comment must be a TwitterCommentInput")
        return TwitterCommentInput.model_validate(
            {"text": sanitize_text(comment.text), "comment_id": comment.comment_id}
        )
