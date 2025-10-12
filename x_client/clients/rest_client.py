"""
Placeholder for an HTTP-based fallback client (e.g., httpx).
"""

from __future__ import annotations

from typing import Any


class RestClient:
    """Skeleton class to be fleshed out when non-tweepy paths are required."""

    def send(self, request: Any) -> Any:  # pragma: no cover - stub
        raise NotImplementedError("RestClient.send is not implemented.")

