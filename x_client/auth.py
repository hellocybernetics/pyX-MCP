"""
Authentication helpers for OAuth workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import tweepy

from x_client.config import ConfigManager, XCredentials
from x_client.exceptions import AuthenticationError, ConfigurationError


class OAuthCallback(Protocol):
    """Callable used to communicate verifier codes or redirect URIs."""

    def __call__(self, authorization_url: str) -> str:
        ...


@dataclass(slots=True)
class OAuthTokens:
    """Container for OAuth access tokens."""

    access_token: str
    access_token_secret: str


class OAuthManager:
    """Manage OAuth 1.0a token acquisition and persistence."""

    def __init__(
        self,
        config_manager: ConfigManager,
        *,
        callback_handler: OAuthCallback | None = None,
        oauth_handler_factory: Callable[..., tweepy.OAuth1UserHandler]
        | None = None,
    ) -> None:
        self._config_manager = config_manager
        self._callback_handler = callback_handler
        self._oauth_handler_factory = oauth_handler_factory or tweepy.OAuth1UserHandler

    def ensure_oauth1_token(self) -> OAuthTokens:
        """
        Return cached OAuth tokens or trigger the interactive flow.
        """

        credentials = self._config_manager.load_credentials()
        if credentials.access_token and credentials.access_token_secret:
            return OAuthTokens(
                access_token=credentials.access_token,
                access_token_secret=credentials.access_token_secret,
            )

        callback = self._callback_handler
        if callback is None:
            raise ConfigurationError(
                "OAuth tokens are missing and no callback handler is available."
            )

        return self.start_oauth1_flow(callback)

    def start_oauth1_flow(self, callback_handler: OAuthCallback | None = None) -> OAuthTokens:
        """Run the OAuth 1.0a flow and persist the resulting tokens."""

        callback = callback_handler or self._callback_handler
        if callback is None:
            raise ConfigurationError("A callback handler is required to start OAuth.")

        credentials = self._config_manager.load_credentials(priority=("env", "dotenv"))
        consumer_key = credentials.api_key
        consumer_secret = credentials.api_secret
        if not consumer_key or not consumer_secret:
            raise ConfigurationError(
                "Consumer API key/secret must be configured before OAuth flow."
            )

        try:
            handler = self._oauth_handler_factory(
                consumer_key,
                consumer_secret,
                callback="oob",
            )
            authorization_url = handler.get_authorization_url()
        except tweepy.TweepyException as exc:  # pragma: no cover - defensive
            raise AuthenticationError("Failed to initialize OAuth flow.") from exc

        verifier = callback(authorization_url)

        try:
            handler.get_access_token(verifier)
        except tweepy.TweepyException as exc:
            raise AuthenticationError("Failed to exchange OAuth verifier.") from exc

        tokens = OAuthTokens(
            access_token=handler.access_token,
            access_token_secret=handler.access_token_secret,
        )
        self._persist_tokens(credentials, tokens)
        return tokens

    def refresh_token(self) -> OAuthTokens:
        """
        For OAuth 1.0a, refreshing means re-running the authorization flow.
        """

        callback = self._callback_handler
        if callback is None:
            raise ConfigurationError(
                "Cannot refresh OAuth tokens without a callback handler."
            )
        return self.start_oauth1_flow(callback)

    def _persist_tokens(
        self, base_credentials: XCredentials, tokens: OAuthTokens
    ) -> None:
        combined = XCredentials(
            api_key=base_credentials.api_key,
            api_secret=base_credentials.api_secret,
            bearer_token=base_credentials.bearer_token,
            access_token=tokens.access_token,
            access_token_secret=tokens.access_token_secret,
        )
        self._config_manager.save_credentials(combined)
