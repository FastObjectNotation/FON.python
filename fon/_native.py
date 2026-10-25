"""
Bridge to the fon_native shared library.

Loads the library, declares the C signatures from include/fon.h and provides
the helpers that the public classes are built on. Nothing in this module is
part of the public API.
"""

from __future__ import annotations

import ctypes
import operator
import os
from array import array
from ctypes import POINTER, byref, c_char_p, c_double, c_float, c_int16, c_int32, c_int64
from ctypes import c_uint8, c_uint32, c_uint64, c_void_p
from typing import Any, List, Optional, Tuple

from ._errors import AlreadyExistsError, FonError, InvalidArgumentError, NotFoundError, StaleViewError, TypeMismatchError


# ---------------------------------------------------------------------------
# Result codes, put modes and kinds (include/fon.h)
# ---------------------------------------------------------------------------

FON_OK: int = 0
FON_ERROR_FILE_NOT_FOUND: int = 1
FON_ERROR_PARSE_FAILED: int = 2
FON_ERROR_WRITE_FAILED: int = 3
FON_ERROR_INVALID_ARGUMENT: int = 4
FON_ERROR_BUFFER_TOO_SMALL: int = 5
FON_ERROR_NOT_FOUND: int = 6
FON_ERROR_TYPE_MISMATCH: int = 7
FON_ERROR_ALREADY_EXISTS: int = 8
FON_ERROR_STALE_VIEW: int = 9

FON_PUT_ADD: int = 0
FON_PUT_SET: int = 1
FON_PUT_UPSERT: int = 2

FON_KIND_ARRAY: int = 0x100

UINT64_MAX: int = 2 ** 64 - 1

# Initial buffer sizes for the first native call. A call that reports
# FON_ERROR_BUFFER_TOO_SMALL is repeated once with the exact size.
GUESS_BYTES: int = 256
GUESS_ITEMS: int = 64
GUESS_HANDLES: int = 16

# array typecodes used for the fixed-width element types
TC_BYTE: str = "B"
TC_SHORT: str = "h"
TC_INT: str = "i"
TC_UINT: str = "I"
TC_LONG: str = "q"
TC_ULONG: str = "Q"
TC_FLOAT: str = "f"
TC_DOUBLE: str = "d"


def _check_typecodes() -> None:
    expected: List[Tuple[str, int]] = [
        (TC_BYTE, 1),
        (TC_SHORT, 2),
        (TC_INT, 4),
        (TC_UINT, 4),
        (TC_LONG, 8),
        (TC_ULONG, 8),
        (TC_FLOAT, 4),
        (TC_DOUBLE, 8),
    ]
    for typecode, size in expected:
        if array(typecode).itemsize != size:
            raise ImportError(f"array typecode {typecode!r} is not {size} bytes on this platform")


_check_typecodes()


# ---------------------------------------------------------------------------
# Locate and load the native library
# ---------------------------------------------------------------------------

def _find_library() -> str:
    """Return the path to fon_native.dll/.so/.dylib bundled with this package."""
    package_dir: str = os.path.dirname(os.path.abspath(__file__))
    repo_root: str = os.path.dirname(package_dir)

    candidates: List[str] = [
        # Development layout: native/target/release/ next to fon/
        os.path.join(repo_root, "native", "target", "release", "fon_native.dll"),
        os.path.join(repo_root, "native", "target", "release", "libfon_native.so"),
        os.path.join(repo_root, "native", "target", "release", "libfon_native.dylib"),
        # Installed wheel layout: bundled alongside the package
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


_lib: Any = ctypes.CDLL(_find_library())


class _FonError(ctypes.Structure):
    """Mirror of the C struct FonError: int32 code, 256-byte NUL-terminated message."""

    _fields_ = [
        ("code", c_int32),
        ("message", c_uint8 * 256),
    ]


_E = POINTER(_FonError)


def _bind(name: str, restype: Any, argtypes: List[Any]) -> Any:
    function: Any = getattr(_lib, name)
    function.restype = restype
    function.argtypes = argtypes
    return function


# ---------------------------------------------------------------------------
# Signatures. One line per function, in the order of include/fon.h.
# ---------------------------------------------------------------------------

fon_version = _bind("fon_version", c_char_p, [])
fon_set_raw_unpack = _bind("fon_set_raw_unpack", None, [c_int32])
fon_set_max_depth = _bind("fon_set_max_depth", None, [c_int32])
fon_buffer_free = _bind("fon_buffer_free", None, [c_void_p, c_int64])

fon_collection_create = _bind("fon_collection_create", c_void_p, [])
fon_collection_free = _bind("fon_collection_free", None, [c_void_p])
fon_collection_size = _bind("fon_collection_size", c_int64, [c_void_p])
fon_collection_clone = _bind("fon_collection_clone", c_void_p, [c_void_p, _E])
fon_collection_kind_of = _bind("fon_collection_kind_of", c_int32, [c_void_p, c_char_p, c_int64])
fon_collection_keys = _bind(
    "fon_collection_keys",
    c_int32,
    [
        c_void_p,
        POINTER(c_int64),
        c_int64,
        c_void_p,
        c_int64,
        POINTER(c_int32),
        POINTER(c_int64),
        POINTER(c_int64),
        _E,
    ],
)
fon_collection_remove = _bind("fon_collection_remove", c_int32, [c_void_p, c_char_p, c_int64])

fon_collection_put_byte = _bind("fon_collection_put_byte", c_int32, [c_void_p, c_char_p, c_int64, c_uint8, c_int32, _E])
fon_collection_put_short = _bind("fon_collection_put_short", c_int32, [c_void_p, c_char_p, c_int64, c_int16, c_int32, _E])
fon_collection_put_int = _bind("fon_collection_put_int", c_int32, [c_void_p, c_char_p, c_int64, c_int32, c_int32, _E])
fon_collection_put_uint = _bind("fon_collection_put_uint", c_int32, [c_void_p, c_char_p, c_int64, c_uint32, c_int32, _E])
fon_collection_put_long = _bind("fon_collection_put_long", c_int32, [c_void_p, c_char_p, c_int64, c_int64, c_int32, _E])
fon_collection_put_ulong = _bind("fon_collection_put_ulong", c_int32, [c_void_p, c_char_p, c_int64, c_uint64, c_int32, _E])
fon_collection_put_float = _bind("fon_collection_put_float", c_int32, [c_void_p, c_char_p, c_int64, c_float, c_int32, _E])
fon_collection_put_double = _bind("fon_collection_put_double", c_int32, [c_void_p, c_char_p, c_int64, c_double, c_int32, _E])
fon_collection_put_bool = _bind("fon_collection_put_bool", c_int32, [c_void_p, c_char_p, c_int64, c_int32, c_int32, _E])
fon_collection_put_string = _bind(
    "fon_collection_put_string", c_int32, [c_void_p, c_char_p, c_int64, c_char_p, c_int64, c_int32, _E]
)
fon_collection_put_raw = _bind(
    "fon_collection_put_raw", c_int32, [c_void_p, c_char_p, c_int64, c_char_p, c_int64, c_int32, _E]
)

fon_collection_put_byte_array = _bind(
    "fon_collection_put_byte_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_short_array = _bind(
    "fon_collection_put_short_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_int_array = _bind(
    "fon_collection_put_int_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_uint_array = _bind(
    "fon_collection_put_uint_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_long_array = _bind(
    "fon_collection_put_long_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_ulong_array = _bind(
    "fon_collection_put_ulong_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_float_array = _bind(
    "fon_collection_put_float_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_double_array = _bind(
    "fon_collection_put_double_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_bool_array = _bind(
    "fon_collection_put_bool_array", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int64, c_int32, _E]
)
fon_collection_put_string_array = _bind(
    "fon_collection_put_string_array",
    c_int32,
    [c_void_p, c_char_p, c_int64, POINTER(c_int64), c_char_p, c_int64, c_int32, _E],
)
fon_collection_put_collection = _bind(
    "fon_collection_put_collection", c_int32, [c_void_p, c_char_p, c_int64, c_void_p, c_int32, _E]
)
fon_collection_put_collection_array = _bind(
    "fon_collection_put_collection_array",
    c_int32,
    [c_void_p, c_char_p, c_int64, POINTER(c_void_p), c_int64, c_int32, _E],
)

fon_collection_get_byte = _bind("fon_collection_get_byte", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_uint8), _E])
fon_collection_get_short = _bind("fon_collection_get_short", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_int16), _E])
fon_collection_get_int = _bind("fon_collection_get_int", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_int32), _E])
fon_collection_get_uint = _bind("fon_collection_get_uint", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_uint32), _E])
fon_collection_get_long = _bind("fon_collection_get_long", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_int64), _E])
fon_collection_get_ulong = _bind("fon_collection_get_ulong", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_uint64), _E])
fon_collection_get_float = _bind("fon_collection_get_float", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_float), _E])
fon_collection_get_double = _bind("fon_collection_get_double", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_double), _E])
fon_collection_get_bool = _bind("fon_collection_get_bool", c_int32, [c_void_p, c_char_p, c_int64, POINTER(c_int32), _E])

_SIZED_GET_ARGTYPES: List[Any] = [c_void_p, c_char_p, c_int64, c_void_p, c_int64, POINTER(c_int64), _E]

fon_collection_get_string = _bind("fon_collection_get_string", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_raw = _bind("fon_collection_get_raw", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_byte_array = _bind("fon_collection_get_byte_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_short_array = _bind("fon_collection_get_short_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_int_array = _bind("fon_collection_get_int_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_uint_array = _bind("fon_collection_get_uint_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_long_array = _bind("fon_collection_get_long_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_ulong_array = _bind("fon_collection_get_ulong_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_float_array = _bind("fon_collection_get_float_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_double_array = _bind("fon_collection_get_double_array", c_int32, _SIZED_GET_ARGTYPES)
fon_collection_get_bool_array = _bind("fon_collection_get_bool_array", c_int32, _SIZED_GET_ARGTYPES)

fon_collection_get_string_array = _bind(
    "fon_collection_get_string_array",
    c_int32,
    [
        c_void_p,
        c_char_p,
        c_int64,
        POINTER(c_int64),
        c_int64,
        c_void_p,
        c_int64,
        POINTER(c_int64),
        POINTER(c_int64),
        _E,
    ],
)
fon_collection_get_collection = _bind("fon_collection_get_collection", c_void_p, [c_void_p, c_char_p, c_int64, _E])
fon_collection_get_collection_array = _bind(
    "fon_collection_get_collection_array",
    c_int32,
    [c_void_p, c_char_p, c_int64, POINTER(c_void_p), c_int64, POINTER(c_int64), _E],
)

fon_dump_create = _bind("fon_dump_create", c_void_p, [])
fon_dump_free = _bind("fon_dump_free", None, [c_void_p])
fon_dump_size = _bind("fon_dump_size", c_int64, [c_void_p])
fon_dump_ids = _bind("fon_dump_ids", c_int32, [c_void_p, c_void_p, c_int64, POINTER(c_int64), _E])
fon_dump_get = _bind("fon_dump_get", c_void_p, [c_void_p, c_uint64])
fon_dump_put = _bind("fon_dump_put", c_int32, [c_void_p, c_uint64, c_void_p, c_int32, _E])
fon_dump_remove = _bind("fon_dump_remove", c_int32, [c_void_p, c_uint64])
fon_dump_remove_many = _bind("fon_dump_remove_many", c_int64, [c_void_p, c_void_p, c_int64])
fon_dump_gens = _bind("fon_dump_gens", c_int32, [c_void_p, c_uint64, POINTER(c_uint32), POINTER(c_uint32)])
fon_dump_touch = _bind("fon_dump_touch", c_int32, [c_void_p, c_uint64])

fon_serialize_dump = _bind("fon_serialize_dump", c_int32, [c_void_p, c_int32, POINTER(c_void_p), POINTER(c_int64), _E])
fon_serialize_collection = _bind(
    "fon_serialize_collection", c_int32, [c_void_p, POINTER(c_void_p), POINTER(c_int64), _E]
)
fon_serialize_to_file = _bind("fon_serialize_to_file", c_int32, [c_void_p, c_char_p, c_int64, c_int32, _E])
fon_deserialize_dump = _bind("fon_deserialize_dump", c_void_p, [c_char_p, c_int64, c_int32, _E])
fon_deserialize_collection = _bind("fon_deserialize_collection", c_void_p, [c_char_p, c_int64, _E])
fon_deserialize_from_file = _bind("fon_deserialize_from_file", c_void_p, [c_char_p, c_int64, c_int32, _E])


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

_ERROR_TYPES: dict = {
    FON_ERROR_INVALID_ARGUMENT: InvalidArgumentError,
    FON_ERROR_NOT_FOUND: NotFoundError,
    FON_ERROR_TYPE_MISMATCH: TypeMismatchError,
    FON_ERROR_ALREADY_EXISTS: AlreadyExistsError,
    FON_ERROR_STALE_VIEW: StaleViewError,
}


def _message_of(err: Optional[_FonError]) -> str:
    if err is None:
        return ""
    raw: bytes = bytes(err.message)
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def make_error(code: int, err: Optional[_FonError]) -> FonError:
    """Build the exception for a native result code, carrying the native message."""
    message: str = _message_of(err)
    if not message:
        message = f"native call failed with code {code}"
    error_type: type = _ERROR_TYPES.get(code, FonError)
    return error_type(code, message)


def check(rc: int, err: _FonError) -> None:
    """Raise the mapped error when a native call returned a non-OK code."""
    if rc != FON_OK:
        raise make_error(rc, err)


def require_handle(handle: Optional[int], err: _FonError, fallback_code: int) -> int:
    """Return a non-null handle, or raise the mapped error for a NULL return."""
    if not handle:
        raise make_error(err.code or fallback_code, err)
    return handle


# ---------------------------------------------------------------------------
# Argument conversion
# ---------------------------------------------------------------------------

def encode_text(text: Any) -> bytes:
    """Encode a str as UTF-8 bytes; the native side receives them with an explicit length."""
    if not isinstance(text, str):
        raise TypeError(f"expected str, got {type(text).__name__}")
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InvalidArgumentError(FON_ERROR_INVALID_ARGUMENT, f"string is not valid UTF-8: {exc}") from None


def path_bytes(path: Any) -> bytes:
    """Encode a file system path (str, bytes or os.PathLike) as UTF-8 bytes."""
    value: Any = os.fspath(path)
    if isinstance(value, bytes):
        return value
    return encode_text(value)


def raw_bytes(value: Any) -> bytes:
    """Accept bytes-like values for raw fields. An int is rejected: bytes(5) would make five zero bytes."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    raise TypeError(f"expected bytes-like value, got {type(value).__name__}")


def _int_in_range(value: Any, low: int, high: int, name: str) -> int:
    number: int = operator.index(value)
    if number < low or number > high:
        raise OverflowError(f"{name} value {number} is outside [{low}, {high}]")
    return number


def _float_value(value: Any) -> float:
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    return float(value)


def arg_u8(value: Any) -> c_uint8:
    return c_uint8(_int_in_range(value, 0, 255, "byte"))


def arg_i16(value: Any) -> c_int16:
    return c_int16(_int_in_range(value, -(2 ** 15), 2 ** 15 - 1, "short"))


def arg_i32(value: Any) -> c_int32:
    return c_int32(_int_in_range(value, -(2 ** 31), 2 ** 31 - 1, "int"))


def arg_u32(value: Any) -> c_uint32:
    return c_uint32(_int_in_range(value, 0, 2 ** 32 - 1, "uint"))


def arg_i64(value: Any) -> c_int64:
    return c_int64(_int_in_range(value, -(2 ** 63), 2 ** 63 - 1, "long"))


def arg_u64(value: Any) -> c_uint64:
    return c_uint64(_int_in_range(value, 0, UINT64_MAX, "ulong"))


def arg_f32(value: Any) -> c_float:
    return c_float(_float_value(value))


def arg_f64(value: Any) -> c_double:
    return c_double(_float_value(value))


def arg_bool(value: Any) -> c_int32:
    return c_int32(1 if value else 0)


def uint64_id(value: Any) -> int:
    """Validate a dump id. Raises OverflowError outside the uint64 range."""
    number: int = operator.index(value)
    if number < 0 or number > UINT64_MAX:
        raise OverflowError(f"id {number} is outside the uint64 range")
    return number


def find_id(value: Any) -> Optional[int]:
    """Return the dump id, or None when it cannot exist in a dump (used by lookups)."""
    number: int = operator.index(value)
    if number < 0 or number > UINT64_MAX:
        return None
    return number


def pack_array(typecode: str, values: Any) -> Tuple[array, int]:
    """
    Copy values into a typed array. Returns the array and the element count.

    The array always holds at least one element so its address is never NULL,
    even when the count is zero.
    """
    items: List[Any] = list(values)
    data: array = array(typecode, items)
    count: int = len(items)
    if count == 0:
        data = array(typecode, [0])
    return data, count


def pack_strings(values: Any) -> Tuple[Any, bytes, int]:
    """Return (lengths, payload, count) for the string-array put functions."""
    encoded: List[bytes] = [encode_text(item) for item in values]
    count: int = len(encoded)
    lengths: Any = (c_int64 * max(1, count))(*[len(item) for item in encoded])
    return lengths, b"".join(encoded), count


def buffer_address(data: array) -> int:
    return data.buffer_info()[0]


# ---------------------------------------------------------------------------
# Output helpers (size-query pattern)
# ---------------------------------------------------------------------------

def read_array(fn: Any, handle: int, typecode: str, key: Optional[bytes]) -> array:
    """
    Read a fixed-width array. Key-less calls (such as fon_dump_ids) pass key=None.

    Tries a small buffer first. On FON_ERROR_BUFFER_TOO_SMALL the exact
    element count is known from `actual`, so the call is repeated once.
    """
    prefix: Tuple[Any, ...] = () if key is None else (key, len(key))
    itemsize: int = array(typecode).itemsize
    err: _FonError = _FonError()
    actual: c_int64 = c_int64(0)
    capacity: int = GUESS_BYTES
    data: array = array(typecode, bytes(capacity * itemsize))
    rc: int = fn(handle, *prefix, buffer_address(data), capacity, byref(actual), byref(err))
    if rc == FON_ERROR_BUFFER_TOO_SMALL:
        capacity = actual.value
        data = array(typecode, bytes(capacity * itemsize))
        rc = fn(handle, *prefix, buffer_address(data), capacity, byref(actual), byref(err))
    check(rc, err)
    return data[: actual.value]


def read_bytes(fn: Any, handle: int, key: bytes) -> bytes:
    """Read a string or raw value (size-query pattern) and return its exact bytes."""
    return read_array(fn, handle, TC_BYTE, key).tobytes()


def read_handles(fn: Any, handle: int, key: bytes) -> List[int]:
    """Read borrowed child handles (collection arrays)."""
    capacity: int = GUESS_HANDLES
    buffer: Any = (c_void_p * capacity)()
    actual: c_int64 = c_int64(0)
    err: _FonError = _FonError()
    rc: int = fn(handle, key, len(key), buffer, capacity, byref(actual), byref(err))
    if rc == FON_ERROR_BUFFER_TOO_SMALL:
        capacity = actual.value
        buffer = (c_void_p * capacity)()
        rc = fn(handle, key, len(key), buffer, capacity, byref(actual), byref(err))
    check(rc, err)
    return [buffer[index] or 0 for index in range(actual.value)]


def read_keys(handle: int) -> List[Tuple[str, int]]:
    """Read (key, kind) pairs in insertion order with one native call on the common path."""
    items: int = GUESS_ITEMS
    byte_capacity: int = GUESS_BYTES
    for attempt in range(2):
        lengths: Any = (c_int64 * items)()
        kinds: Any = (c_int32 * items)()
        data: array = array(TC_BYTE, bytes(byte_capacity))
        count: c_int64 = c_int64(0)
        total: c_int64 = c_int64(0)
        err: _FonError = _FonError()
        rc: int = fon_collection_keys(
            handle,
            lengths,
            items,
            buffer_address(data),
            byte_capacity,
            kinds,
            byref(count),
            byref(total),
            byref(err),
        )
        if rc == FON_ERROR_BUFFER_TOO_SMALL and attempt == 0:
            items = max(1, count.value)
            byte_capacity = max(1, total.value)
            continue
        check(rc, err)
        raw: bytes = data[: total.value].tobytes()
        result: List[Tuple[str, int]] = []
        position: int = 0
        for index in range(count.value):
            length: int = lengths[index]
            result.append((raw[position: position + length].decode("utf-8"), kinds[index]))
            position += length
        return result
    raise FonError(FON_ERROR_BUFFER_TOO_SMALL, "keys did not fit after resizing the buffer")


def read_strings(fn: Any, handle: int, key: bytes) -> List[str]:
    """Read a string array with the multi-string pattern."""
    items: int = GUESS_ITEMS
    byte_capacity: int = GUESS_BYTES
    for attempt in range(2):
        lengths: Any = (c_int64 * items)()
        data: array = array(TC_BYTE, bytes(byte_capacity))
        count: c_int64 = c_int64(0)
        total: c_int64 = c_int64(0)
        err: _FonError = _FonError()
        rc: int = fn(
            handle,
            key,
            len(key),
            lengths,
            items,
            buffer_address(data),
            byte_capacity,
            byref(count),
            byref(total),
            byref(err),
        )
        if rc == FON_ERROR_BUFFER_TOO_SMALL and attempt == 0:
            items = max(1, count.value)
            byte_capacity = max(1, total.value)
            continue
        check(rc, err)
        raw: bytes = data[: total.value].tobytes()
        result: List[str] = []
        position: int = 0
        for index in range(count.value):
            length: int = lengths[index]
            result.append(raw[position: position + length].decode("utf-8"))
            position += length
        return result
    raise FonError(FON_ERROR_BUFFER_TOO_SMALL, "string array did not fit after resizing the buffer")


def take_output(fn: Any, *args: Any) -> bytes:
    """
    Call a serialize function that returns a library-owned buffer through
    (out, out_len, err), copy the bytes and release the buffer.
    """
    out: c_void_p = c_void_p()
    out_len: c_int64 = c_int64(0)
    err: _FonError = _FonError()
    rc: int = fn(*args, byref(out), byref(out_len), byref(err))
    check(rc, err)
    try:
        if not out.value or out_len.value == 0:
            return b""
        return ctypes.string_at(out.value, out_len.value)
    finally:
        if out.value:
            fon_buffer_free(out.value, out_len.value)
