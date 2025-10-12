"""
Post related workflows built on top of client adapters.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, Sequence

from x_client.exceptions import ApiResponseError, ThreadCreationError, XClientError
from x_client.models import Post, PostDeleteResult, RepostResult
from x_client.utils import split_text_for_thread


EventHook = Callable[[str, dict[str, Any]], None]


class PostClient(Protocol):
    """Protocol subset consumed by the service."""

    def create_post(self, **kwargs: Any) -> Any:
        ...

    def delete_post(self, post_id: str) -> Any:
        ...

    def get_post(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def search_recent_posts(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def repost_post(self, post_id: str) -> Any:
        ...

    def undo_repost(self, post_id: str) -> Any:
        ...


@dataclass(slots=True)
class PostService:
    """High level orchestration for post CRUD operations."""

    client: PostClient
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger(__name__)
    )
    event_hook: EventHook | None = None

    @dataclass(slots=True)
    class ThreadCreateResult:
        """Outcome of a thread creation attempt."""

        posts: list[Post]
        error: XClientError | None = None
        failed_index: int | None = None
        rolled_back: bool = False

        @property
        def succeeded(self) -> bool:
            return self.error is None

    def create_post(
        self,
        text: str,
        *,
        media_ids: Iterable[str] | None = None,
        in_reply_to: str | None = None,
        quote_post_id: str | None = None,
        reply_settings: str | None = None,
        **extra: Any,
    ) -> Post:
        self.logger.info(
            "post.create.start",
            extra={
                "event": "post.create.start",
                "has_media": bool(media_ids),
                "text_len": len(text),
            },
        )
        self._emit_event(
            "post.create.start",
            {"has_media": bool(media_ids), "extra_keys": list(extra.keys())},
        )

        payload: dict[str, Any] = {"text": text}
        if media_ids:
            media_id_list = [int(media_id) for media_id in media_ids]
            payload["media_ids"] = media_id_list
            payload["user_auth"] = True
        if in_reply_to:
            payload["in_reply_to_tweet_id"] = in_reply_to
        if quote_post_id:
            payload["quote_post_id"] = quote_post_id
        if reply_settings:
            payload["reply_settings"] = reply_settings
        payload.update(extra)

        try:
            response = self.client.create_post(**payload)
        except XClientError as exc:
            self.logger.exception(
                "post.create.error",
                extra={
                    "event": "post.create.error",
                    "error": str(exc),
                },
            )
            self._emit_event(
                "post.create.error",
                {"error": str(exc), "payload_keys": list(payload.keys())},
            )
            raise

        post = Post.from_api(response)

        self.logger.info(
            "post.create.success",
            extra={
                "event": "post.create.success",
                "post_id": post.id,
                "has_media": bool(payload.get("media_ids")),
            },
        )
        self._emit_event(
            "post.create.success",
            {"post_id": post.id, "has_media": bool(payload.get("media_ids"))},
        )
        return post

    def delete_post(self, post_id: str) -> bool:
        response = self.client.delete_post(post_id)
        result = PostDeleteResult.from_api(response)
        if not result.deleted:
            raise ApiResponseError(f"Unable to delete post '{post_id}'.")
        return True

    def get_post(self, post_id: str, **kwargs: Any) -> Post:
        response = self.client.get_post(post_id, **kwargs)
        return Post.from_api(response)

    def search_recent(
        self,
        query: str,
        *,
        max_results: int | None = None,
        expansions: Iterable[str] | None = None,
        post_fields: Iterable[str] | None = None,
        user_fields: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> list[Post]:
        payload_kwargs: dict[str, Any] = {}
        if max_results is not None:
            payload_kwargs["max_results"] = max_results
        if expansions:
            payload_kwargs["expansions"] = list(expansions)
        if post_fields:
            payload_kwargs["tweet_fields"] = list(post_fields)
        if user_fields:
            payload_kwargs["user_fields"] = list(user_fields)
        payload_kwargs.update(kwargs)

        response = self.client.search_recent_posts(query, **payload_kwargs)
        data = getattr(response, "data", response)
        if not data:
            return []

        includes = getattr(response, "includes", None)

        if isinstance(data, list):
            return [Post.from_api(item, includes=includes) for item in data]

        # When tweepy returns a single Post instance rather than list
        return [Post.from_api(data, includes=includes)]

    def repost_post(self, post_id: str) -> RepostResult:
        response = self.client.repost_post(post_id)
        result = self._parse_repost_state(response)
        if not result.reposted:
            raise ApiResponseError(f"Unable to repost '{post_id}'.")
        self.logger.info(
            "post.repost.success",
            extra={"event": "post.repost.success", "post_id": post_id},
        )
        self._emit_event(
            "post.repost.success",
            {"post_id": post_id, "reposted": result.reposted},
        )
        return result

    def undo_repost(self, post_id: str) -> RepostResult:
        response = self.client.undo_repost(post_id)
        result = self._parse_repost_state(response)
        if result.reposted:
            raise ApiResponseError(f"Unable to undo repost '{post_id}'.")
        self.logger.info(
            "post.repost.undo.success",
            extra={"event": "post.repost.undo.success", "post_id": post_id},
        )
        self._emit_event(
            "post.repost.undo.success",
            {"post_id": post_id, "reposted": result.reposted},
        )
        return result

    # ------------------------------------------------------------------
    # Thread operations
    # ------------------------------------------------------------------

    def create_thread(
        self,
        text: str | Iterable[str],
        *,
        chunk_limit: int = 280,
        in_reply_to: str | None = None,
        rollback_on_failure: bool = True,
        segment_pause: float = 0.0,
        **extra: Any,
    ) -> ThreadCreateResult:
        """Create a thread by splitting text and chaining replies.

        Args:
            text: Source text or iterable of pre-split segments.
            chunk_limit: Maximum characters per post (default 280).
            in_reply_to: Optional post ID to anchor the first entry.
            rollback_on_failure: Delete successfully created posts when a
                later segment fails to post.
            segment_pause: Seconds to wait between successful segments to
                avoid hitting posting rate limits (default 0.0).
            **extra: Additional kwargs forwarded to ``create_post``.

        Returns:
            ThreadCreateResult describing the outcome.
        """

        segments = self._normalize_thread_segments(text, chunk_limit=chunk_limit)
        self.logger.info(
            "post.thread.start",
            extra={
                "event": "post.thread.start",
                "segment_count": len(segments),
                "has_anchor": bool(in_reply_to),
            },
        )
        self._emit_event(
            "post.thread.start",
            {
                "segment_count": len(segments),
                "in_reply_to": in_reply_to,
                "extra_keys": list(extra.keys()),
            },
        )
        posts: list[Post] = []
        base_kwargs = dict(extra)
        base_kwargs.pop("in_reply_to", None)
        base_kwargs.pop("text", None)

        anchor = in_reply_to
        for index, segment in enumerate(segments):
            call_kwargs = dict(base_kwargs)
            if anchor:
                call_kwargs["in_reply_to"] = anchor

            try:
                post = self.create_post(segment, **call_kwargs)
            except XClientError as exc:  # e.g. ApiResponseError, RateLimitExceeded
                rolled_back = False
                if rollback_on_failure and posts:
                    rolled_back = self._rollback_posts(posts)
                self.logger.error(
                    "post.thread.segment_failed",
                    extra={
                        "event": "post.thread.segment_failed",
                        "failed_index": index,
                        "rolled_back": rolled_back,
                    },
                )
                self._emit_event(
                    "post.thread.error",
                    {
                        "failed_index": index,
                        "rolled_back": rolled_back,
                        "error": str(exc),
                    },
                )
                return self.ThreadCreateResult(
                    posts=posts,
                    error=exc,
                    failed_index=index,
                    rolled_back=rolled_back,
                )

            posts.append(post)
            anchor = post.id
            self.logger.debug(
                "post.thread.segment_success",
                extra={
                    "event": "post.thread.segment_success",
                    "segment_index": index,
                    "post_id": post.id,
                },
            )
            self._emit_event(
                "post.thread.segment_success",
                {"segment_index": index, "post_id": post.id},
            )

            if segment_pause > 0 and index < len(segments) - 1:
                self.logger.debug(
                    "post.thread.pause",
                    extra={
                        "event": "post.thread.pause",
                        "segment_index": index,
                        "next_segment_index": index + 1,
                        "segment_pause": segment_pause,
                    },
                )
                self._emit_event(
                    "post.thread.pause",
                    {
                        "segment_index": index,
                        "segment_pause": segment_pause,
                    },
                )
                time.sleep(segment_pause)

        self.logger.info(
            "post.thread.success",
            extra={
                "event": "post.thread.success",
                "segment_count": len(posts),
            },
        )
        self._emit_event(
            "post.thread.success",
            {
                "segment_count": len(posts),
                "post_ids": [post.id for post in posts],
            },
        )
        return self.ThreadCreateResult(posts=posts)

    # Internal helpers -------------------------------------------------

    def _normalize_thread_segments(
        self, text: str | Iterable[str], *, chunk_limit: int
    ) -> list[str]:
        if isinstance(text, str):
            segments = split_text_for_thread(text, limit=chunk_limit)
        else:
            segments = [segment.strip() for segment in text if segment is not None]

        segments = [segment for segment in segments if segment]
        if not segments:
            raise ThreadCreationError(
                "Thread text produced no segments.",
                posts=[],
                failed_index=0,
                cause=ValueError("No content to post."),
            )

        return segments

    def _rollback_posts(self, posts: Sequence[Post]) -> bool:
        success = True
        for post in reversed(posts):
            try:
                self.delete_post(post.id)
            except XClientError:
                success = False
                self.logger.warning(
                    "post.thread.rollback_failed",
                    extra={
                        "event": "post.thread.rollback_failed",
                        "post_id": post.id,
                    },
                )
        return success

    def _parse_repost_state(self, payload: Any) -> RepostResult:
        try:
            return RepostResult.from_api(payload)
        except (TypeError, ValueError) as exc:
            raise ApiResponseError("Unexpected repost response payload.") from exc

    def _emit_event(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_hook is None:
            return
        try:
            self.event_hook(name, payload)
        except Exception:  # pragma: no cover - defensive
            self.logger.exception(
                "post.event_hook.error",
                extra={"event": "post.event_hook.error", "hook_event": name},
            )
