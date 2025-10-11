"""
Tweet related workflows built on top of client adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from twitter_client.exceptions import ApiResponseError
from twitter_client.models import Tweet, TweetDeleteResult


class TweetClient(Protocol):
    """Protocol subset consumed by the service."""

    def create_tweet(self, **kwargs: Any) -> Any:
        ...

    def delete_tweet(self, tweet_id: str) -> Any:
        ...

    def get_tweet(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def search_recent_tweets(self, *args: Any, **kwargs: Any) -> Any:
        ...


@dataclass(slots=True)
class TweetService:
    """High level orchestration for tweet CRUD operations."""

    client: TweetClient

    def create_tweet(
        self,
        text: str,
        *,
        media_ids: Iterable[str] | None = None,
        in_reply_to: str | None = None,
        quote_tweet_id: str | None = None,
        reply_settings: str | None = None,
        **extra: Any,
    ) -> Tweet:
        payload: dict[str, Any] = {"text": text}
        if media_ids:
            payload["media_ids"] = list(media_ids)
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        if quote_tweet_id:
            payload["quote_tweet_id"] = quote_tweet_id
        if reply_settings:
            payload["reply_settings"] = reply_settings
        payload.update(extra)
        response = self.client.create_tweet(**payload)
        return Tweet.from_api(response)

    def delete_tweet(self, tweet_id: str) -> bool:
        response = self.client.delete_tweet(tweet_id)
        result = TweetDeleteResult.from_api(response)
        if not result.deleted:
            raise ApiResponseError(f"Unable to delete tweet '{tweet_id}'.")
        return True

    def get_tweet(self, tweet_id: str, **kwargs: Any) -> Tweet:
        response = self.client.get_tweet(tweet_id, **kwargs)
        return Tweet.from_api(response)

    def search_recent(self, query: str, **kwargs: Any) -> list[Tweet]:
        response = self.client.search_recent_tweets(query, **kwargs)
        data = getattr(response, "data", response)
        if not data:
            return []

        if isinstance(data, list):
            return [Tweet.from_api(item) for item in data]

        # When tweepy returns a single Tweet instance rather than list
        return [Tweet.from_api(data)]

