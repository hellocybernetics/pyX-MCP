"""
x_client package scaffolding.

This module exposes the public entry points that higher-level applications
will import. It intentionally remains minimal at this stage and will be
expanded as concrete implementations land.
"""

__all__ = [
    "config",
    "auth",
    "clients",
    "services",
    "exceptions",
    "models",
    "rate_limit",
]


def __getattr__(name: str):
    """
    Provide a helpful error message for yet-to-be-implemented modules.

    Stubbing this ensures early feedback if downstream code imports symbols
    before their definitions are in place, aligning with the error-handling
    guidelines.
    """
    raise AttributeError(
        f"Module attribute '{name}' is not yet implemented in x_client."
    )

