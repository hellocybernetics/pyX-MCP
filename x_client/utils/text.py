"""Text processing helpers."""

from __future__ import annotations

import re


def split_text_for_thread(text: str, *, limit: int = 280) -> list[str]:
    """Split *text* into thread-sized chunks honoring word boundaries.

    Args:
        text: Source text to split.
        limit: Maximum number of characters allowed per chunk.

    Returns:
        List of text fragments, each with length <= ``limit``.

    Raises:
        ValueError: If ``limit`` is not a positive integer.
    """

    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    stripped = text.strip()
    if not stripped:
        return [""]

    if len(stripped) <= limit:
        return [stripped]

    tokens = re.split(r"(\s+)", stripped)
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current.rstrip())
            current = ""

    for token in tokens:
        if token is None or token == "":
            continue

        token_len = len(token)
        if token_len > limit:
            flush()
            for start in range(0, token_len, limit):
                chunks.append(token[start : start + limit])
            continue

        if len(current) + token_len <= limit:
            current += token
            continue

        flush()
        current = token.lstrip() if token[0].isspace() else token

    flush()

    # Ensure we do not return empty fragments.
    return [chunk for chunk in chunks if chunk]

