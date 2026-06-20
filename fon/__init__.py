"""
fon — Fast Object Notation serialization for Python.

FON is a compact, human-readable, line-oriented format where each line is one
record containing typed key/value pairs.  Public API:

  - native_version()                   -> str
  - set_raw_unpack(bool)               — configure raw-unpack mode
  - set_max_depth(int)                 — configure max nesting depth
  - FonCollection                      — key/value map
        Scalars:  add_int, add_long, add_float, add_double, add_bool, add_string
                  get_int, get_long, get_float, get_double, get_bool, get_string
        Arrays:   add_int_array / get_int_array (list[int])
                  add_float_array / get_float_array (list[float])
        Nested:   add_collection / get_collection  (ownership transfer on add)
                  add_collection_array / get_collection_array
        Misc:     serialize, FonCollection.deserialize(line)
  - FonDump                            — id→collection store
        add, get, size, serialize, FonDump.deserialize(text)
        serialize_to_file(path)
  - deserialize_dump_from_file(path)   -> FonDump  (module-level)
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import c_int32, c_int64, c_uint64, c_double, c_float, c_char_p, c_void_p, c_uint8
from typing import List, Optional


# ---------------------------------------------------------------------------
# Locate and load the native library
# ---------------------------------------------------------------------------

def _find_library() -> str:
    """Return the path to fon_native.dll/.so/.dylib bundled with this package."""
    package_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(package_dir)

    candidates = [
        # Development layout: native/target/release/ next to fon/
        os.path.join(repo_root, "native", "target", "release", "fon_native.dll"),
        os.path.join(repo_root, "native", "target", "release", "libfon_native.so"),
        os.path.join(repo_root, "native", "target", "release", "libfon_native.dylib"),
        # Installed wheel layout: bundled alongside __init__.py
        os.path.join(package_dir, "fon_native.dll"),
        os.path.join(package_dir, "libfon_native.so"),
        os.path.join(package_dir, "libfon_native.dylib"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Cannot find fon_native shared library. "
        "Run `cargo build --release --manifest-path native/Cargo.toml` first. "
        f"Searched: {candidates}"
    )


_lib_path = _find_library()
_lib = ctypes.CDLL(_lib_path)


# ---------------------------------------------------------------------------
# FonError C struct  (i32 code + 256-byte message)
# ---------------------------------------------------------------------------

class _FonError(ctypes.Structure):
    _fields_ = [
        ("code", c_int32),
        ("message", ctypes.c_uint8 * 256),
    ]

    def raise_if_error(self) -> None:
        if self.code != 0:
            msg = bytes(self.message).rstrip(b"\x00").decode("utf-8", errors="replace")
            raise FonError(self.code, msg)


# ---------------------------------------------------------------------------
# Result codes
# ---------------------------------------------------------------------------

FON_OK = 0
FON_ERROR_FILE_NOT_FOUND = 1
FON_ERROR_PARSE_FAILED = 2
FON_ERROR_WRITE_FAILED = 3
FON_ERROR_INVALID_ARGUMENT = 4


class FonError(Exception):
    """Raised when the native library returns a non-zero result code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[fon error {code}] {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Helper: configure argtypes / restype for each ABI function
# ---------------------------------------------------------------------------

_err_p = ctypes.POINTER(_FonError)

# fon_version
_lib.fon_version.argtypes = []
_lib.fon_version.restype = ctypes.c_char_p

# fon_dump_create / free / size / get
_lib.fon_dump_create.argtypes = []
_lib.fon_dump_create.restype = c_void_p

_lib.fon_dump_free.argtypes = [c_void_p]
_lib.fon_dump_free.restype = None

_lib.fon_dump_size.argtypes = [c_void_p]
_lib.fon_dump_size.restype = c_int64

_lib.fon_dump_get.argtypes = [c_void_p, c_uint64]
_lib.fon_dump_get.restype = c_void_p

_lib.fon_dump_add.argtypes = [c_void_p, c_uint64, c_void_p, _err_p]
_lib.fon_dump_add.restype = c_int32

# fon_collection_create / free / size
_lib.fon_collection_create.argtypes = []
_lib.fon_collection_create.restype = c_void_p

_lib.fon_collection_free.argtypes = [c_void_p]
_lib.fon_collection_free.restype = None

_lib.fon_collection_size.argtypes = [c_void_p]
_lib.fon_collection_size.restype = c_int64

# add_int / long / float / double / bool / string
_lib.fon_collection_add_int.argtypes = [c_void_p, c_char_p, c_int32, _err_p]
_lib.fon_collection_add_int.restype = c_int32

_lib.fon_collection_add_long.argtypes = [c_void_p, c_char_p, c_int64, _err_p]
_lib.fon_collection_add_long.restype = c_int32

_lib.fon_collection_add_float.argtypes = [c_void_p, c_char_p, c_float, _err_p]
_lib.fon_collection_add_float.restype = c_int32

_lib.fon_collection_add_double.argtypes = [c_void_p, c_char_p, c_double, _err_p]
_lib.fon_collection_add_double.restype = c_int32

_lib.fon_collection_add_bool.argtypes = [c_void_p, c_char_p, c_int32, _err_p]
_lib.fon_collection_add_bool.restype = c_int32

_lib.fon_collection_add_string.argtypes = [c_void_p, c_char_p, c_char_p, _err_p]
_lib.fon_collection_add_string.restype = c_int32

# get_int / long / float / double / bool / string
_lib.fon_collection_get_int.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_int32), _err_p
]
_lib.fon_collection_get_int.restype = c_int32

_lib.fon_collection_get_long.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_int64), _err_p
]
_lib.fon_collection_get_long.restype = c_int32

_lib.fon_collection_get_float.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_float), _err_p
]
_lib.fon_collection_get_float.restype = c_int32

_lib.fon_collection_get_double.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_double), _err_p
]
_lib.fon_collection_get_double.restype = c_int32

_lib.fon_collection_get_bool.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_int32), _err_p
]
_lib.fon_collection_get_bool.restype = c_int32

# get_string: (collection, key, buffer, buffer_size, error) -> int
# The C function writes a null-terminated string into buffer.
# We need to call it with enough buffer space; we first query size via serialize.
_lib.fon_collection_get_string.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_uint8), c_int64, _err_p
]
_lib.fon_collection_get_string.restype = c_int32

# buffer serialization (two-call pattern)
_lib.fon_serialize_dump_to_buffer.argtypes = [
    c_void_p,
    ctypes.POINTER(c_uint8),
    c_int64,
    ctypes.POINTER(c_int64),
    c_int32,
    _err_p,
]
_lib.fon_serialize_dump_to_buffer.restype = c_int32

_lib.fon_serialize_collection_to_buffer.argtypes = [
    c_void_p,
    ctypes.POINTER(c_uint8),
    c_int64,
    ctypes.POINTER(c_int64),
    _err_p,
]
_lib.fon_serialize_collection_to_buffer.restype = c_int32

# buffer deserialization
_lib.fon_deserialize_dump_from_buffer.argtypes = [
    ctypes.POINTER(c_uint8),
    c_int64,
    c_int32,
    _err_p,
]
_lib.fon_deserialize_dump_from_buffer.restype = c_void_p

_lib.fon_deserialize_collection_from_buffer.argtypes = [
    ctypes.POINTER(c_uint8),
    c_int64,
    _err_p,
]
_lib.fon_deserialize_collection_from_buffer.restype = c_void_p

# configuration
_lib.fon_set_raw_unpack.argtypes = [c_int32]
_lib.fon_set_raw_unpack.restype = None

_lib.fon_set_max_depth.argtypes = [c_int32]
_lib.fon_set_max_depth.restype = None

# file I/O
_lib.fon_serialize_to_file.argtypes = [c_void_p, c_char_p, c_int32, _err_p]
_lib.fon_serialize_to_file.restype = c_int32

_lib.fon_deserialize_from_file.argtypes = [c_char_p, c_int32, _err_p]
_lib.fon_deserialize_from_file.restype = c_void_p

# add_int_array / add_float_array
_lib.fon_collection_add_int_array.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_int32), c_int64, _err_p
]
_lib.fon_collection_add_int_array.restype = c_int32

_lib.fon_collection_add_float_array.argtypes = [
    c_void_p, c_char_p, ctypes.POINTER(c_float), c_int64, _err_p
]
_lib.fon_collection_add_float_array.restype = c_int32

# get_int_array / get_float_array  (two-call: buffer=NULL → size; then fill)
_lib.fon_collection_get_int_array.argtypes = [
    c_void_p, c_char_p,
    ctypes.POINTER(c_int32), c_int64, ctypes.POINTER(c_int64),
    _err_p,
]
_lib.fon_collection_get_int_array.restype = c_int32

_lib.fon_collection_get_float_array.argtypes = [
    c_void_p, c_char_p,
    ctypes.POINTER(c_float), c_int64, ctypes.POINTER(c_int64),
    _err_p,
]
_lib.fon_collection_get_float_array.restype = c_int32

# add_collection / get_collection
_lib.fon_collection_add_collection.argtypes = [c_void_p, c_char_p, c_void_p, _err_p]
_lib.fon_collection_add_collection.restype = c_int32

_lib.fon_collection_get_collection.argtypes = [c_void_p, c_char_p, _err_p]
_lib.fon_collection_get_collection.restype = c_void_p

# add_collection_array / get_collection_array
_lib.fon_collection_add_collection_array.argtypes = [
    c_void_p, c_char_p,
    ctypes.POINTER(c_void_p), c_int64,
    _err_p,
]
_lib.fon_collection_add_collection_array.restype = c_int32

_lib.fon_collection_get_collection_array.argtypes = [
    c_void_p, c_char_p,
    ctypes.POINTER(c_void_p), c_int64, ctypes.POINTER(c_int64),
    _err_p,
]
_lib.fon_collection_get_collection_array.restype = c_int32


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _encode_key(key: str) -> bytes:
    return key.encode("utf-8")


def _two_call_serialize_collection(handle: int) -> bytes:
    """Use the two-call pattern to serialize a collection handle to UTF-8 bytes."""
    err = _FonError()
    required = c_int64(0)
    rc = _lib.fon_serialize_collection_to_buffer(
        handle, None, c_int64(0), ctypes.byref(required), ctypes.byref(err)
    )
    if rc != FON_OK:
        err.raise_if_error()
    size = required.value
    if size == 0:
        return b""
    buf = (c_uint8 * size)()
    rc = _lib.fon_serialize_collection_to_buffer(
        handle, buf, c_int64(size), ctypes.byref(required), ctypes.byref(err)
    )
    if rc != FON_OK:
        err.raise_if_error()
    return bytes(buf)


def _two_call_serialize_dump(handle: int, max_threads: int = 0) -> bytes:
    """Use the two-call pattern to serialize a dump handle to UTF-8 bytes."""
    err = _FonError()
    required = c_int64(0)
    rc = _lib.fon_serialize_dump_to_buffer(
        handle, None, c_int64(0), ctypes.byref(required), c_int32(max_threads), ctypes.byref(err)
    )
    if rc != FON_OK:
        err.raise_if_error()
    size = required.value
    if size == 0:
        return b""
    buf = (c_uint8 * size)()
    rc = _lib.fon_serialize_dump_to_buffer(
        handle, buf, c_int64(size), ctypes.byref(required), c_int32(max_threads), ctypes.byref(err)
    )
    if rc != FON_OK:
        err.raise_if_error()
    return bytes(buf)


# ---------------------------------------------------------------------------
# Public API — native_version(), set_raw_unpack(), set_max_depth()
# ---------------------------------------------------------------------------

def native_version() -> str:
    """Return the version string embedded in the native fon_native library."""
    raw = _lib.fon_version()
    if raw is None:
        return ""
    return raw.decode("utf-8")


def set_raw_unpack(enable: bool) -> None:
    """
    Enable or disable raw-unpack mode for deserialization.

    When enabled the deserializer treats raw bytes as literal values rather
    than interpreting escape sequences.  Default is False.
    """
    _lib.fon_set_raw_unpack(c_int32(1 if enable else 0))


def set_max_depth(depth: int) -> None:
    """
    Set the maximum nesting depth for deserialization.

    Values below 1 are clamped to 1 by the native library.  Default is 64.
    """
    _lib.fon_set_max_depth(c_int32(depth))


# ---------------------------------------------------------------------------
# Module-level file I/O
# ---------------------------------------------------------------------------

def deserialize_dump_from_file(path: str, max_threads: int = 0) -> "FonDump":
    """
    Read a FON dump file from disk and return a new FonDump.

    Parameters
    ----------
    path:
        Absolute or relative file path (UTF-8).
    max_threads:
        Threading hint passed to the native library (0 = single-threaded).
    """
    err = _FonError()
    handle = _lib.fon_deserialize_from_file(
        path.encode("utf-8"), c_int32(max_threads), ctypes.byref(err)
    )
    if not handle:
        err.raise_if_error()
        raise FonError(FON_ERROR_FILE_NOT_FOUND, f"fon_deserialize_from_file returned null for: {path}")
    return FonDump(_handle=handle)


# ---------------------------------------------------------------------------
# FonCollection
# ---------------------------------------------------------------------------

class FonCollection:
    """
    A key→value collection.  Wraps a heap-allocated FonCollection from fon_native.

    Ownership: by default this object owns the native handle and will free it on
    __del__.  When a collection is passed to FonDump.add() the ownership is
    transferred to the dump; in that case the Python object must no longer be used.
    """

    def __init__(self, _handle: Optional[int] = None, *, _owns: bool = True) -> None:
        """
        Create a new empty collection, or wrap an existing native handle.

        Parameters
        ----------
        _handle:
            If None (the default) a new native FonCollection is allocated.
            If an integer, it is used as the raw pointer (borrowed or owned
            depending on `_owns`).
        _owns:
            Whether this Python object is responsible for freeing the handle.
        """
        if _handle is None:
            self._handle: int = _lib.fon_collection_create()
            if not self._handle:
                raise MemoryError("fon_collection_create returned null")
            self._owns = True
        else:
            self._handle = _handle
            self._owns = _owns
        self._transferred = False

    def _require_alive(self) -> None:
        if self._transferred:
            raise RuntimeError(
                "This FonCollection handle has been transferred to a FonDump and must not be used."
            )

    def __del__(self) -> None:
        if self._owns and not self._transferred and self._handle:
            _lib.fon_collection_free(self._handle)
            self._handle = 0

    def __len__(self) -> int:
        self._require_alive()
        return int(_lib.fon_collection_size(self._handle))

    # ---- add methods -------------------------------------------------------

    def add_int(self, key: str, value: int) -> None:
        """Add an i32 value."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_int(
            self._handle, _encode_key(key), c_int32(value), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_long(self, key: str, value: int) -> None:
        """Add an i64 value."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_long(
            self._handle, _encode_key(key), c_int64(value), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_float(self, key: str, value: float) -> None:
        """Add an f32 value."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_float(
            self._handle, _encode_key(key), c_float(value), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_double(self, key: str, value: float) -> None:
        """Add an f64 value."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_double(
            self._handle, _encode_key(key), c_double(value), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_bool(self, key: str, value: bool) -> None:
        """Add a boolean value (stored as i32 0/1 in C ABI)."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_bool(
            self._handle, _encode_key(key), c_int32(1 if value else 0), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_string(self, key: str, value: str) -> None:
        """Add a string value."""
        self._require_alive()
        err = _FonError()
        rc = _lib.fon_collection_add_string(
            self._handle,
            _encode_key(key),
            value.encode("utf-8"),
            ctypes.byref(err),
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_int_array(self, key: str, values: List[int]) -> None:
        """Add an array of i32 values."""
        self._require_alive()
        count = len(values)
        arr = (c_int32 * count)(*values)
        err = _FonError()
        rc = _lib.fon_collection_add_int_array(
            self._handle, _encode_key(key), arr, c_int64(count), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_float_array(self, key: str, values: List[float]) -> None:
        """Add an array of f32 values."""
        self._require_alive()
        count = len(values)
        arr = (c_float * count)(*values)
        err = _FonError()
        rc = _lib.fon_collection_add_float_array(
            self._handle, _encode_key(key), arr, c_int64(count), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()

    def add_collection(self, key: str, child: "FonCollection") -> None:
        """
        Nest a child collection under key.

        Ownership transfer: after this call the child handle is owned by this
        collection.  The child FonCollection must not be used again.
        """
        self._require_alive()
        if child._transferred:
            raise RuntimeError(
                "Cannot add an already-transferred FonCollection."
            )
        err = _FonError()
        rc = _lib.fon_collection_add_collection(
            self._handle, _encode_key(key), child._handle, ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        child._transferred = True
        child._owns = False

    def add_collection_array(self, key: str, children: List["FonCollection"]) -> None:
        """
        Nest an array of child collections under key.

        Ownership transfer: after this call every child handle is owned by this
        collection.  None of the children must be used again.
        """
        self._require_alive()
        for child in children:
            if child._transferred:
                raise RuntimeError(
                    "Cannot add an already-transferred FonCollection."
                )
        count = len(children)
        arr = (c_void_p * count)(*(c._handle for c in children))
        err = _FonError()
        rc = _lib.fon_collection_add_collection_array(
            self._handle, _encode_key(key), arr, c_int64(count), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        for child in children:
            child._transferred = True
            child._owns = False

    # ---- get methods -------------------------------------------------------

    def get_int(self, key: str) -> int:
        """Get an i32 value by key."""
        self._require_alive()
        err = _FonError()
        out = c_int32(0)
        rc = _lib.fon_collection_get_int(
            self._handle, _encode_key(key), ctypes.byref(out), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return int(out.value)

    def get_long(self, key: str) -> int:
        """Get an i64 value by key."""
        self._require_alive()
        err = _FonError()
        out = c_int64(0)
        rc = _lib.fon_collection_get_long(
            self._handle, _encode_key(key), ctypes.byref(out), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return int(out.value)

    def get_float(self, key: str) -> float:
        """Get an f32 value by key."""
        self._require_alive()
        err = _FonError()
        out = c_float(0.0)
        rc = _lib.fon_collection_get_float(
            self._handle, _encode_key(key), ctypes.byref(out), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return float(out.value)

    def get_double(self, key: str) -> float:
        """Get an f64 value by key."""
        self._require_alive()
        err = _FonError()
        out = c_double(0.0)
        rc = _lib.fon_collection_get_double(
            self._handle, _encode_key(key), ctypes.byref(out), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return float(out.value)

    def get_bool(self, key: str) -> bool:
        """Get a boolean value by key."""
        self._require_alive()
        err = _FonError()
        out = c_int32(0)
        rc = _lib.fon_collection_get_bool(
            self._handle, _encode_key(key), ctypes.byref(out), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return out.value != 0

    def get_string(self, key: str, buffer_size: int = 4096) -> str:
        """
        Get a string value by key.

        Parameters
        ----------
        key:
            The field key.
        buffer_size:
            Internal buffer size in bytes. Must be larger than the UTF-8 byte
            length of the stored string plus one (for the null terminator).
            Default 4096 bytes covers most practical strings.
        """
        self._require_alive()
        err = _FonError()
        buf = (c_uint8 * buffer_size)()
        rc = _lib.fon_collection_get_string(
            self._handle,
            _encode_key(key),
            buf,
            c_int64(buffer_size),
            ctypes.byref(err),
        )
        if rc != FON_OK:
            err.raise_if_error()
        raw = bytes(buf)
        nul = raw.find(b"\x00")
        if nul >= 0:
            raw = raw[:nul]
        return raw.decode("utf-8")

    def get_int_array(self, key: str) -> List[int]:
        """
        Get an i32 array by key (two-call pattern: query size, then fill).
        """
        self._require_alive()
        err = _FonError()
        actual = c_int64(0)
        # First call: buffer=NULL to query count.
        rc = _lib.fon_collection_get_int_array(
            self._handle, _encode_key(key), None, c_int64(0),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        count = actual.value
        if count == 0:
            return []
        buf = (c_int32 * count)()
        err = _FonError()
        rc = _lib.fon_collection_get_int_array(
            self._handle, _encode_key(key), buf, c_int64(count),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return list(buf)

    def get_float_array(self, key: str) -> List[float]:
        """
        Get an f32 array by key (two-call pattern: query size, then fill).
        """
        self._require_alive()
        err = _FonError()
        actual = c_int64(0)
        rc = _lib.fon_collection_get_float_array(
            self._handle, _encode_key(key), None, c_int64(0),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        count = actual.value
        if count == 0:
            return []
        buf = (c_float * count)()
        err = _FonError()
        rc = _lib.fon_collection_get_float_array(
            self._handle, _encode_key(key), buf, c_int64(count),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return [float(v) for v in buf]

    def get_collection(self, key: str) -> "FonCollection":
        """
        Get a borrowed handle to a nested collection under key.

        The returned FonCollection is borrowed — do NOT free it or transfer it
        to another collection or dump.
        """
        self._require_alive()
        err = _FonError()
        handle = _lib.fon_collection_get_collection(
            self._handle, _encode_key(key), ctypes.byref(err)
        )
        if not handle:
            err.raise_if_error()
            raise FonError(
                FON_ERROR_INVALID_ARGUMENT,
                f"fon_collection_get_collection returned null for key: {key!r}",
            )
        return FonCollection(_handle=handle, _owns=False)

    def get_collection_array(self, key: str) -> List["FonCollection"]:
        """
        Get borrowed handles to an array of nested collections under key.

        The returned FonCollection objects are borrowed — do NOT free them or
        transfer them to another collection or dump.
        Uses the two-call pattern: first query count, then fill.
        """
        self._require_alive()
        err = _FonError()
        actual = c_int64(0)
        # First call: buffer=NULL to query count.
        rc = _lib.fon_collection_get_collection_array(
            self._handle, _encode_key(key), None, c_int64(0),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        count = actual.value
        if count == 0:
            return []
        buf = (c_void_p * count)()
        err = _FonError()
        rc = _lib.fon_collection_get_collection_array(
            self._handle, _encode_key(key), buf, c_int64(count),
            ctypes.byref(actual), ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        return [FonCollection(_handle=buf[i], _owns=False) for i in range(count)]

    # ---- serialization -----------------------------------------------------

    def serialize(self) -> str:
        """Serialize this collection to a single FON line (UTF-8 string)."""
        self._require_alive()
        return _two_call_serialize_collection(self._handle).decode("utf-8")

    @classmethod
    def deserialize(cls, line: str) -> "FonCollection":
        """Parse a single FON line and return a new FonCollection."""
        data = line.encode("utf-8")
        buf = (c_uint8 * len(data))(*data)
        err = _FonError()
        handle = _lib.fon_deserialize_collection_from_buffer(
            buf, c_int64(len(data)), ctypes.byref(err)
        )
        if not handle:
            err.raise_if_error()
            raise FonError(FON_ERROR_PARSE_FAILED, "fon_deserialize_collection_from_buffer returned null")
        return cls(_handle=handle, _owns=True)

    def __repr__(self) -> str:
        if self._transferred:
            return "<FonCollection (transferred)>"
        try:
            return f"<FonCollection {self.serialize()!r}>"
        except Exception:
            return "<FonCollection>"


# ---------------------------------------------------------------------------
# FonDump
# ---------------------------------------------------------------------------

class FonDump:
    """
    An id→FonCollection store.  Wraps a heap-allocated FonDump from fon_native.

    After calling add(id, collection), the collection's ownership is transferred
    to the dump; the passed FonCollection must not be used afterwards.
    """

    def __init__(self, _handle: Optional[int] = None) -> None:
        if _handle is None:
            self._handle: int = _lib.fon_dump_create()
            if not self._handle:
                raise MemoryError("fon_dump_create returned null")
        else:
            self._handle = _handle

    def __del__(self) -> None:
        if self._handle:
            _lib.fon_dump_free(self._handle)
            self._handle = 0

    def __len__(self) -> int:
        return int(_lib.fon_dump_size(self._handle))

    def add(self, id: int, collection: FonCollection) -> None:
        """
        Add a collection to this dump under the given id.

        Ownership transfer: after this call, collection must not be used again.
        """
        if collection._transferred:
            raise RuntimeError("Cannot add an already-transferred FonCollection.")
        err = _FonError()
        rc = _lib.fon_dump_add(
            self._handle, c_uint64(id), collection._handle, ctypes.byref(err)
        )
        if rc != FON_OK:
            err.raise_if_error()
        # Mark the Python wrapper as no longer owning the handle.
        collection._transferred = True
        collection._owns = False

    def get(self, id: int) -> Optional[FonCollection]:
        """
        Return a borrowed FonCollection at the given id, or None if absent.

        The returned FonCollection is borrowed — do NOT free it or add it
        to another dump.
        """
        handle = _lib.fon_dump_get(self._handle, c_uint64(id))
        if not handle:
            return None
        return FonCollection(_handle=handle, _owns=False)

    def serialize(self, max_threads: int = 0) -> str:
        """Serialize this dump to a multi-line FON string."""
        return _two_call_serialize_dump(self._handle, max_threads).decode("utf-8")

    def serialize_to_file(self, path: str, max_threads: int = 0) -> None:
        """
        Write this dump to a file on disk.

        Parameters
        ----------
        path:
            Absolute or relative file path (UTF-8).
        max_threads:
            Threading hint passed to the native library (0 = single-threaded).
        """
        err = _FonError()
        rc = _lib.fon_serialize_to_file(
            self._handle,
            path.encode("utf-8"),
            c_int32(max_threads),
            ctypes.byref(err),
        )
        if rc != FON_OK:
            err.raise_if_error()

    @classmethod
    def deserialize(cls, text: str, max_threads: int = 0) -> "FonDump":
        """Parse a multi-line FON string and return a new FonDump."""
        data = text.encode("utf-8")
        buf = (c_uint8 * len(data))(*data)
        err = _FonError()
        handle = _lib.fon_deserialize_dump_from_buffer(
            buf, c_int64(len(data)), c_int32(max_threads), ctypes.byref(err)
        )
        if not handle:
            err.raise_if_error()
            raise FonError(FON_ERROR_PARSE_FAILED, "fon_deserialize_dump_from_buffer returned null")
        return cls(_handle=handle)

    def __repr__(self) -> str:
        return f"<FonDump size={len(self)}>"


__all__ = [
    "native_version",
    "set_raw_unpack",
    "set_max_depth",
    "deserialize_dump_from_file",
    "FonCollection",
    "FonDump",
    "FonError",
    "FON_OK",
    "FON_ERROR_FILE_NOT_FOUND",
    "FON_ERROR_PARSE_FAILED",
    "FON_ERROR_WRITE_FAILED",
    "FON_ERROR_INVALID_ARGUMENT",
]
