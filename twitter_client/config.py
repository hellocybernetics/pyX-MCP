"""
Configuration management utilities for twitter_client.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from twitter_client.exceptions import ConfigurationError

ENV_VAR_MAP = {
    "api_key": "TWITTER_API_KEY",
    "api_secret": "TWITTER_API_SECRET",
    "access_token": "TWITTER_ACCESS_TOKEN",
    "access_token_secret": "TWITTER_ACCESS_TOKEN_SECRET",
    "bearer_token": "TWITTER_BEARER_TOKEN",
}


class CredentialsProvider(Protocol):
    """Abstract provider used to decouple persistence from runtime usage."""

    def load(self) -> "TwitterCredentials":
        raise NotImplementedError

    def save(self, credentials: "TwitterCredentials") -> None:
        raise NotImplementedError


@dataclass(slots=True)
class TwitterCredentials:
    """Credential container supporting OAuth 1.0a and OAuth 2.0 tokens."""

    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    access_token_secret: str | None = None
    bearer_token: str | None = None

    def is_empty(self) -> bool:
        return all(
            value in (None, "")
            for value in (
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret,
                self.bearer_token,
            )
        )

    def merge(self, other: "TwitterCredentials") -> "TwitterCredentials":
        """Merge credential sets, preferring non-null values from ``other``."""

        return TwitterCredentials(
            api_key=other.api_key or self.api_key,
            api_secret=other.api_secret or self.api_secret,
            access_token=other.access_token or self.access_token,
            access_token_secret=other.access_token_secret or self.access_token_secret,
            bearer_token=other.bearer_token or self.bearer_token,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in asdict(self).items()
            if isinstance(value, str) and value
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, str | None]) -> "TwitterCredentials":
        return cls(
            api_key=data.get("api_key"),
            api_secret=data.get("api_secret"),
            access_token=data.get("access_token"),
            access_token_secret=data.get("access_token_secret"),
            bearer_token=data.get("bearer_token"),
        )


class ConfigManager:
    """Loads and persists credentials from environment variables or disk."""

    def __init__(
        self,
        credential_path: Path | None = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._credential_path = credential_path or Path("credentials/twitter_config.json")
        self._env = env or os.environ

    def load_credentials(
        self,
        priority: Sequence[str] = ("env", "file"),
    ) -> TwitterCredentials:
        """
        Load credentials according to the requested priority order.

        Raises:
            ConfigurationError: when no credentials are available.
        """

        for source in priority:
            if source == "env":
                credentials = self._load_from_env()
            elif source == "file":
                credentials = self._load_from_file()
            else:
                raise ValueError(f"Unknown credential source '{source}'.")

            if credentials and not credentials.is_empty():
                return credentials

        raise ConfigurationError("Twitter credentials are not configured.")

    def save_credentials(self, credentials: TwitterCredentials) -> None:
        """Persist credentials to disk, merging with existing values."""

        existing = self._load_from_file()
        merged = existing.merge(credentials) if existing else credentials

        self._credential_path.parent.mkdir(parents=True, exist_ok=True)
        with self._credential_path.open("w", encoding="utf-8") as fp:
            json.dump(merged.to_dict(), fp, indent=2, sort_keys=True)

        # Set file permissions to owner read/write only for security
        os.chmod(self._credential_path, 0o600)

    def _load_from_env(self) -> TwitterCredentials | None:
        values: dict[str, str | None] = {
            field: self._env.get(env_name) for field, env_name in ENV_VAR_MAP.items()
        }
        credentials = TwitterCredentials.from_mapping(values)
        return credentials if not credentials.is_empty() else None

    def _load_from_file(self) -> TwitterCredentials | None:
        if not self._credential_path.exists():
            return None

        with self._credential_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)

        if not isinstance(data, Mapping):
            raise ConfigurationError(
                f"Credential file {self._credential_path} did not contain a mapping."
            )

        credentials = TwitterCredentials.from_mapping(data)
        return credentials if not credentials.is_empty() else None

