"""
Client adapters encapsulate concrete HTTP integrations such as tweepy.

Individual client modules will expose thin wrappers that translate provider
specific exceptions into the library's domain exceptions.
"""

__all__ = [
    "tweepy_client",
    "rest_client",
]

