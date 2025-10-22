"""Text processing helpers.

This module now supports pluggable text split strategies (Strategy pattern)
for thread segmentation. The historical `split_text_for_thread` function
remains the primary entry point and preserves its default behavior, but can
optionally accept a strategy name or object.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class TextSplitStrategy(Protocol):
    """Protocol for split strategies used by thread segmentation."""

    def split(self, text: str, *, limit: int) -> list[str]:
        ...


@dataclass(slots=True)
class WordBoundaryStrategy:
    """Default, historical behavior: split on whitespace with hard wrap fallback."""

    def split(self, text: str, *, limit: int) -> list[str]:
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
            if not token:
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
        return [chunk for chunk in chunks if chunk]


@dataclass(slots=True)
class SentenceBoundaryStrategy:
    """Sentence-aware split for English/Japanese punctuation, then pack <= limit.

    This is intentionally light-weight (regex-based). It first splits into
    candidate sentences and then greedily packs them into chunks not exceeding
    ``limit``. When a single sentence exceeds ``limit``, it falls back to a
    word-boundary hard wrap within that sentence.
    """

    _word_strategy: WordBoundaryStrategy = WordBoundaryStrategy()

    _sentence_re = re.compile(
        r"""
        # Capture sentences ending with English or CJK terminators
        (?:
            [^.!?。！？\n]+         # sentence body (no terminators/newline)
            (?:[.!?。！？]+)         # one or more end punctuations
        )
        |
        (?:\S.+?$)                 # fallback for trailing fragment without terminator
        """,
        re.VERBOSE | re.MULTILINE,
    )

    def split(self, text: str, *, limit: int) -> list[str]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

        stripped = text.strip()
        if not stripped:
            return [""]

        sentences = [s.strip() for s in self._sentence_re.findall(stripped) if s.strip()]
        if not sentences:
            return self._word_strategy.split(stripped, limit=limit)

        chunks: list[str] = []
        current = ""

        def flush() -> None:
            nonlocal current
            if current:
                chunks.append(current)
                current = ""

        for sent in sentences:
            if len(sent) <= limit:
                if not current:
                    current = sent
                elif len(current) + 1 + len(sent) <= limit:
                    current = f"{current} {sent}"
                else:
                    flush()
                    current = sent
                continue

            # Over-long sentence: fallback to word strategy and pack piecewise
            sub = self._word_strategy.split(sent, limit=limit)
            for piece in sub:
                if not current:
                    current = piece
                elif len(current) + 1 + len(piece) <= limit:
                    current = f"{current} {piece}"
                else:
                    flush()
                    current = piece

        flush()
        return chunks


@dataclass(slots=True)
class ParagraphStrategy:
    """Paragraph-first split: break by blank lines, then pack, with safe fallback.

    Each paragraph is kept whole if it fits within ``limit``; otherwise the
    paragraph is further split using the word-boundary strategy.
    """

    _word_strategy: WordBoundaryStrategy = WordBoundaryStrategy()

    def split(self, text: str, *, limit: int) -> list[str]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

        stripped = text.strip()
        if not stripped:
            return [""]

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", stripped) if p.strip()]
        if not paragraphs:
            paragraphs = [stripped]

        chunks: list[str] = []
        current = ""

        def emit(fragment: str) -> None:
            nonlocal current
            if not current:
                current = fragment
            elif len(current) + 1 + len(fragment) <= limit:
                current = f"{current} {fragment}"
            else:
                chunks.append(current)
                current = fragment

        for para in paragraphs:
            if len(para) <= limit:
                emit(para)
                continue
            for piece in self._word_strategy.split(para, limit=limit):
                emit(piece)

        if current:
            chunks.append(current)
        return chunks


def get_split_strategy(name: str) -> TextSplitStrategy:
    """Return a named split strategy.

    Supported names: "simple" (default), "sentence", "paragraph".
    """
    key = (name or "").strip().lower()
    if key in ("", "simple", "default", "word"):
        return WordBoundaryStrategy()
    if key in ("sentence", "sentences", "sbd"):
        return SentenceBoundaryStrategy()
    if key in ("paragraph", "paragraphs", "para"):
        return ParagraphStrategy()
    raise ValueError(f"Unknown split strategy '{name}'.")


def split_text_for_thread(
    text: str,
    *,
    limit: int = 280,
    strategy: str | TextSplitStrategy | None = None,
) -> list[str]:
    """Split ``text`` into thread-sized chunks using a pluggable strategy.

    Backward-compatible: when ``strategy`` is omitted, the historical
    word-boundary behavior is used.
    """

    impl: TextSplitStrategy
    if strategy is None:
        impl = WordBoundaryStrategy()
    elif isinstance(strategy, str):
        impl = get_split_strategy(strategy)
    else:
        impl = strategy

    chunks = impl.split(text, limit=limit)
    # Ensure we do not return empty fragments.
    return [c for c in chunks if c]
