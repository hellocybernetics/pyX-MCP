"""
Rate limiting utilities and retry/backoff helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(slots=True)
class RateLimitStatus:
    """Represents parsed rate limit metadata from Twitter headers."""

    limit: int
    remaining: int
    reset_at: datetime


class SleepStrategy(Protocol):
    """Strategy responsible for sleeping/backing off."""

    def __call__(self, seconds: float) -> None:
        raise NotImplementedError


def compute_backoff(status: RateLimitStatus) -> float:
    """Placeholder for the actual backoff calculation logic."""

    now = datetime.now(timezone.utc)
    delta = (status.reset_at - now).total_seconds()
    return max(delta, 0.0)

