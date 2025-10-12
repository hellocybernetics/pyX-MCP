"""
Configuration management utilities for x_client.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from x_client.exceptions import ConfigurationError

ENV_VAR_MAP = {
    "api_key": "X_API_KEY",
    "api_secret": "X_API_SECRET",
    "access_token": "X_ACCESS_TOKEN",
    "access_token_secret": "X_ACCESS_TOKEN_SECRET",
    "bearer_token": "X_BEARER_TOKEN",
}


class CredentialsProvider(Protocol):
    """Abstract provider used to decouple persistence from runtime usage."""

    def load(self) -> "XCredentials":
        raise NotImplementedError

    def save(self, credentials: "XCredentials") -> None:
        raise NotImplementedError


@dataclass(slots=True)
class XCredentials:
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

    def merge(self, other: "XCredentials") -> "XCredentials":
        """Merge credential sets, preferring non-null values from ``other``."""

        return XCredentials(
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
    def from_mapping(cls, data: Mapping[str, str | None]) -> "XCredentials":
        return cls(
            api_key=data.get("api_key"),
            api_secret=data.get("api_secret"),
            access_token=data.get("access_token"),
            access_token_secret=data.get("access_token_secret"),
            bearer_token=data.get("bearer_token"),
        )


class ConfigManager:
    """Load and persist credentials from environment variables or a .env file."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        dotenv_path: Path | str | None = None,
    ) -> None:
        self._env = env or os.environ
        self._dotenv_path = Path(dotenv_path) if dotenv_path else Path(".env")

    def load_credentials(
        self,
        priority: Sequence[str] = ("env", "dotenv"),
    ) -> XCredentials:
        """
        Load credentials according to the requested priority order.

        Raises:
            ConfigurationError: when no credentials are available.
        """

        for source in priority:
            if source == "env":
                credentials = self._load_from_env()
            elif source == "dotenv":
                credentials = self._load_from_dotenv()
            else:
                raise ValueError(f"Unknown credential source '{source}'.")

            if credentials and not credentials.is_empty():
                return credentials

        raise ConfigurationError("X (Twitter) credentials are not configured.")

    def save_credentials(self, credentials: XCredentials) -> None:
        """Persist credentials to .env, merging with existing values."""

        existing = self._load_from_dotenv()
        merged = existing.merge(credentials) if existing else credentials
        self._write_to_dotenv(merged)

    def _load_from_env(self) -> XCredentials | None:
        values: dict[str, str | None] = {
            field: self._env.get(env_name) for field, env_name in ENV_VAR_MAP.items()
        }
        credentials = XCredentials.from_mapping(values)
        return credentials if not credentials.is_empty() else None

    def _load_from_dotenv(self) -> XCredentials | None:
        path = self._dotenv_path
        if not path.exists() or not path.is_file():
            return None

        values: dict[str, str | None] = {key: None for key in ENV_VAR_MAP}

        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if "=" not in stripped:
                continue

            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            value = raw_value.strip().strip('"').strip("'")

            for field, env_name in ENV_VAR_MAP.items():
                if key == env_name:
                    values[field] = value or None
                    break

        credentials = XCredentials.from_mapping(values)
        return credentials if not credentials.is_empty() else None

    def _write_to_dotenv(self, credentials: XCredentials) -> None:
        path = self._dotenv_path
        existing_lines: list[str] = []
        if path.exists():
            existing_lines = path.read_text(encoding="utf-8").splitlines()

        env_values = {
            env_name: getattr(credentials, field)
            for field, env_name in ENV_VAR_MAP.items()
            if getattr(credentials, field)
        }

        # Track which variables we have updated to avoid duplicates
        seen_keys: set[str] = set()
        updated_lines: list[str] = []

        for line in existing_lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or "=" not in line:
                updated_lines.append(line)
                continue

            key, _ = line.split("=", 1)
            key = key.strip()
            if key in env_values:
                updated_lines.append(f"{key}={env_values[key]}")
                seen_keys.add(key)
            else:
                updated_lines.append(line)

        # Append any new keys that were not present previously
        for key, value in env_values.items():
            if key not in seen_keys:
                updated_lines.append(f"{key}={value}")

        if not updated_lines:
            updated_lines.append("# X (Twitter) API credentials")
            for key, value in env_values.items():
                updated_lines.append(f"{key}={value}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
