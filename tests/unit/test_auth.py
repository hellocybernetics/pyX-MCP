from __future__ import annotations

import pytest
import tweepy

from x_client.auth import OAuthManager, OAuthTokens
from x_client.config import ConfigManager
from x_client.exceptions import AuthenticationError, ConfigurationError


class DummyOAuthHandler:
    def __init__(self, consumer_key: str, consumer_secret: str, callback: str | None = None) -> None:
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.callback = callback
        self.access_token = "new-access-token"
        self.access_token_secret = "new-access-secret"
        self._verifier: str | None = None

    def get_authorization_url(self) -> str:
        return "https://twitter.com/oauth/authorize"

    def get_access_token(self, verifier: str) -> str:
        self._verifier = verifier
        return self.access_token


def test_ensure_oauth1_token_returns_cached_tokens(tmp_path) -> None:
    env = {
        "X_API_KEY": "api-key",
        "X_API_SECRET": "api-secret",
        "X_ACCESS_TOKEN": "cached-access",
        "X_ACCESS_TOKEN_SECRET": "cached-secret",
    }
    manager = ConfigManager(env=env, dotenv_path=tmp_path / ".env")
    oauth = OAuthManager(manager)

    tokens = oauth.ensure_oauth1_token()
    assert tokens == OAuthTokens(access_token="cached-access", access_token_secret="cached-secret")


def test_start_oauth1_flow_persists_tokens(tmp_path) -> None:
    env = {
        "X_API_KEY": "api-key",
        "X_API_SECRET": "api-secret",
    }
    dotenv_path = tmp_path / ".env"
    manager = ConfigManager(env=env, dotenv_path=dotenv_path)

    def factory(*args, **kwargs):
        return DummyOAuthHandler(*args, **kwargs)

    def callback(url: str) -> str:
        assert "oauth" in url
        return "verifier-code"

    oauth = OAuthManager(manager, callback_handler=callback, oauth_handler_factory=factory)  # type: ignore[arg-type]
    tokens = oauth.ensure_oauth1_token()

    assert tokens.access_token == "new-access-token"
    data = dotenv_path.read_text(encoding="utf-8")
    assert "new-access-secret" in data


def test_start_oauth1_flow_raises_on_auth_failure(tmp_path) -> None:
    env = {
        "X_API_KEY": "api-key",
        "X_API_SECRET": "api-secret",
    }
    manager = ConfigManager(env=env, dotenv_path=tmp_path / ".env")

    class FailingHandler(DummyOAuthHandler):
        def get_authorization_url(self) -> str:
            raise tweepy.errors.TweepyException("boom")

    def factory(*args, **kwargs):
        return FailingHandler(*args, **kwargs)

    oauth = OAuthManager(manager, callback_handler=lambda _: "code", oauth_handler_factory=factory)  # type: ignore[arg-type]

    with pytest.raises(AuthenticationError):
        oauth.start_oauth1_flow()


def test_refresh_token_requires_callback(tmp_path) -> None:
    manager = ConfigManager(
        env={
            "X_API_KEY": "api-key",
            "X_API_SECRET": "api-secret",
        },
        dotenv_path=tmp_path / ".env",
    )
    oauth = OAuthManager(manager)

    with pytest.raises(ConfigurationError):
        oauth.refresh_token()
