"""
Exception types raised by the fon package.

Every error carries the native result code and the native message. The more
specific subclasses are raised for the codes that callers commonly handle.
"""

from __future__ import annotations


class FonError(Exception):
    """Base class for errors reported by the native library."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(code, message)
        self.code: int = code
        self.message: str = message

    def __str__(self) -> str:
        return f"[fon error {self.code}] {self.message}"


class NotFoundError(FonError, KeyError):
    """A key or record id is absent (FON_ERROR_NOT_FOUND)."""


class TypeMismatchError(FonError, TypeError):
    """A key exists but holds a value of another type (FON_ERROR_TYPE_MISMATCH)."""


class AlreadyExistsError(FonError):
    """An add was attempted for a key or id that already exists (FON_ERROR_ALREADY_EXISTS)."""


class StaleViewError(FonError):
    """A view refers to a value that was changed or removed since the view was created (FON_ERROR_STALE_VIEW)."""


class InvalidArgumentError(FonError, ValueError):
    """An argument was rejected, for example a key with a reserved character (FON_ERROR_INVALID_ARGUMENT)."""
