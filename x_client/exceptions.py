"""
Domain specific exception hierarchy for the x_client package.
"""

class XClientError(Exception):
    """Base exception for all library errors."""


class ConfigurationError(XClientError):
    """Raised when required configuration or credentials are missing."""


class AuthenticationError(XClientError):
    """Raised when authentication flow fails or tokens are invalid."""


class ApiResponseError(XClientError):
    """Raised when the X API returns an error payload."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class RateLimitExceeded(ApiResponseError):
    """Raised when the X API enforces a rate limit."""

    def __init__(self, message: str, *, reset_at: int | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class MediaValidationError(XClientError):
    """Raised when local media files do not satisfy upload requirements."""


class MediaProcessingTimeout(ApiResponseError):
    """Raised when media processing does not complete in the allocated time."""


class MediaProcessingFailed(ApiResponseError):
    """Raised when the API reports failure for an uploaded media asset."""
