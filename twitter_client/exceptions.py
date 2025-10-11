"""
Domain specific exception hierarchy for the twitter_client package.
"""

class TwitterClientError(Exception):
    """Base exception for all library errors."""


class ConfigurationError(TwitterClientError):
    """Raised when required configuration or credentials are missing."""


class AuthenticationError(TwitterClientError):
    """Raised when authentication flow fails or tokens are invalid."""


class ApiResponseError(TwitterClientError):
    """Raised when the Twitter API returns an error payload."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class RateLimitExceeded(ApiResponseError):
    """Raised when the Twitter API enforces a rate limit."""

    def __init__(self, message: str, *, reset_at: int | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class MediaValidationError(TwitterClientError):
    """Raised when local media files do not satisfy upload requirements."""


class MediaProcessingTimeout(ApiResponseError):
    """Raised when media processing does not complete in the allocated time."""


class MediaProcessingFailed(ApiResponseError):
    """Raised when the API reports failure for an uploaded media asset."""
