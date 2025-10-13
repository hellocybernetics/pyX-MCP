"""
Client adapters encapsulate concrete HTTP integrations such as tweepy.

Individual client modules will expose thin wrappers that translate provider
specific exceptions into the library's domain exceptions.
"""

from __future__ import annotations

from .rate_limited_client import RateLimitedClient
from .rest_client import RestClient
from .tweepy_client import TweepyClient

__all__ = [
    "RateLimitedClient",
    "RestClient",
    "TweepyClient",
]

