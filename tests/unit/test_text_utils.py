from __future__ import annotations

import pytest

from x_client.utils import split_text_for_thread


def test_split_text_for_thread_respects_limit() -> None:
    text = "This is a sample sentence that should wrap nicely across multiple tweets."
    chunks = split_text_for_thread(text, limit=25)

    assert all(len(chunk) <= 25 for chunk in chunks)
    assert "".join(chunk.strip() + " " for chunk in chunks).strip().startswith("This is a sample")


def test_split_text_for_thread_handles_long_word() -> None:
    text = "a" * 600
    chunks = split_text_for_thread(text, limit=280)

    assert len(chunks) == 3
    assert chunks[0] == "a" * 280
    assert chunks[1] == "a" * 280
    assert chunks[2] == "a" * 40


def test_split_text_for_thread_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError):
        split_text_for_thread("hello", limit=0)

