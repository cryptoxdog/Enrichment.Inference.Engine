"""
Core exceptions for the Enrichment Engine.

Custom exception classes for configuration errors, dependency injection guards,
and other domain-specific error conditions.
"""

from __future__ import annotations


class DependencyNotConfiguredError(RuntimeError):
    """Raised when a required dependency is not configured at app startup.

    Use this instead of NotImplementedError for FastAPI dependency injection
    guards. NotImplementedError semantically means "subclass must implement"
    (abstract method pattern), while this exception indicates a configuration
    issue that should fail loudly if dependencies are not wired.

    Example:
        def get_score_engine():
            raise DependencyNotConfiguredError(
                "ScoreEngine",
                "Call configure_score_dependencies() in lifespan"
            )
    """

    def __init__(self, dependency_name: str, hint: str = "") -> None:
        message = f"{dependency_name} not configured"
        if hint:
            message += f". {hint}"
        super().__init__(message)
        self.dependency_name = dependency_name
        self.hint = hint
