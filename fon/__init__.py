"""
fon: Fast Object Notation serialization for Python.

FON is a compact, human-readable, line-oriented format in which each line is
one record of typed key/value pairs. Values can nest.

Public API:

  - FonCollection   key to typed value map (owned, record view or nested view)
  - FonDump         id to collection store
  - FonKind         (type, is_array) named tuple returned by FonCollection.kind()
  - FonError and its subclasses InvalidArgumentError, NotFoundError,
    TypeMismatchError, AlreadyExistsError, StaleViewError
  - deserialize_dump_from_file(path)
  - native_version(), set_raw_unpack(enable), set_max_depth(depth)
"""

from __future__ import annotations

from . import _native as _n
from ._collection import FonCollection
from ._dump import FonDump, deserialize_dump_from_file
from ._errors import AlreadyExistsError, FonError, InvalidArgumentError, NotFoundError, StaleViewError, TypeMismatchError
from ._kinds import FonKind


__version__ = "0.4.0"

FON_OK = _n.FON_OK
FON_ERROR_FILE_NOT_FOUND = _n.FON_ERROR_FILE_NOT_FOUND
FON_ERROR_PARSE_FAILED = _n.FON_ERROR_PARSE_FAILED
FON_ERROR_WRITE_FAILED = _n.FON_ERROR_WRITE_FAILED
FON_ERROR_INVALID_ARGUMENT = _n.FON_ERROR_INVALID_ARGUMENT
FON_ERROR_BUFFER_TOO_SMALL = _n.FON_ERROR_BUFFER_TOO_SMALL
FON_ERROR_NOT_FOUND = _n.FON_ERROR_NOT_FOUND
FON_ERROR_TYPE_MISMATCH = _n.FON_ERROR_TYPE_MISMATCH
FON_ERROR_ALREADY_EXISTS = _n.FON_ERROR_ALREADY_EXISTS
FON_ERROR_STALE_VIEW = _n.FON_ERROR_STALE_VIEW


def native_version() -> str:
    """Return the version string embedded in the native fon_native library."""
    raw: bytes = _n.fon_version() or b""
    return raw.decode("utf-8")


def set_raw_unpack(enable: bool) -> None:
    """
    Enable or disable raw-unpack mode for deserialization.

    When enabled, raw (binary) values are decoded during parsing. Default is False.
    """
    _n.fon_set_raw_unpack(1 if enable else 0)


def set_max_depth(depth: int) -> None:
    """
    Set the maximum nesting depth for deserialization.

    Values below 1 are clamped to 1 by the native library. Default is 64.
    """
    _n.fon_set_max_depth(int(depth))


__all__ = [
    "native_version",
    "set_raw_unpack",
    "set_max_depth",
    "deserialize_dump_from_file",
    "FonCollection",
    "FonDump",
    "FonKind",
    "FonError",
    "InvalidArgumentError",
    "NotFoundError",
    "TypeMismatchError",
    "AlreadyExistsError",
    "StaleViewError",
    "FON_OK",
    "FON_ERROR_FILE_NOT_FOUND",
    "FON_ERROR_PARSE_FAILED",
    "FON_ERROR_WRITE_FAILED",
    "FON_ERROR_INVALID_ARGUMENT",
    "FON_ERROR_BUFFER_TOO_SMALL",
    "FON_ERROR_NOT_FOUND",
    "FON_ERROR_TYPE_MISMATCH",
    "FON_ERROR_ALREADY_EXISTS",
    "FON_ERROR_STALE_VIEW",
]
