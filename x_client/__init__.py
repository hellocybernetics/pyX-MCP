"""Public package interface for the X (Twitter) client library."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import tomllib
from typing import TYPE_CHECKING

from .config import ConfigManager, XCredentials
from .factory import XClientFactory
from .integrations.mcp_adapter import XMCPAdapter
from .rate_limit import RateLimitHandler, RetryConfig
from .services.media_service import MediaService
from .services.post_service import PostService

if TYPE_CHECKING:  # pragma: no cover - only for static type checkers
    from .integrations.mcp_server import XMCPServer


def _detect_version() -> str:
    try:
        return version("pyx-mcp")
    except PackageNotFoundError:  # pragma: no cover - fallback for local source usage
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject.exists():
            with pyproject.open("rb") as handle:
                data = tomllib.load(handle)
            return data.get("project", {}).get("version", "0.0.0")
        return "0.0.0"


__version__ = _detect_version()

# Re-export frequently used modules to keep import paths concise when the
# library is embedded in external projects.
config = import_module("x_client.config")
auth = import_module("x_client.auth")
clients = import_module("x_client.clients")
services = import_module("x_client.services")
exceptions = import_module("x_client.exceptions")
models = import_module("x_client.models")
rate_limit = import_module("x_client.rate_limit")


__all__ = [
    "__version__",
    "ConfigManager",
    "XCredentials",
    "XClientFactory",
    "XMCPAdapter",
    "RateLimitHandler",
    "RetryConfig",
    "MediaService",
    "PostService",
    "config",
    "auth",
    "clients",
    "services",
    "exceptions",
    "models",
    "rate_limit",
    "XMCPServer",
]


def __getattr__(name: str):
    if name == "XMCPServer":
        from .integrations.mcp_server import XMCPServer as _XMCPServer

        return _XMCPServer
    raise AttributeError(name)
