"""
FonCollection: an owned collection, a record view or a nested view.

Views never own native memory. Each view keeps a strong reference to its root
(the dump, or the owned root collection), so the native tree stays alive while
the view is reachable. Before every access a view checks the generations and
versions it captured and raises StaleViewError when the value it refers to has
been changed or removed.
"""

from __future__ import annotations

from ctypes import byref, c_double, c_float, c_int16, c_int32, c_int64, c_uint8, c_uint32, c_uint64, c_void_p
from typing import Any, List, Optional, Tuple

from . import _native as _n
from ._errors import FonError, InvalidArgumentError, NotFoundError, StaleViewError
from ._kinds import FonKind, kind_from_code


_CLOSED_MESSAGE: str = "this FonCollection has been closed or transferred and must not be used"
_OWNER_MESSAGE: str = "the collection or dump that owns this view has been closed or transferred"
_TRANSFERRED_OWNER_MESSAGE: str = "the collection that owns this view was stored in another container; read it again from there"
_STALE_MESSAGE: str = "the value behind this view was changed or removed; read it again from its owner"


class FonCollection:
    """
    A key to value collection of typed FON values.

    Three kinds of object share this class:

    - an owned collection, created by FonCollection(), clone() or deserialize();
      it owns native memory and releases it on close() or when collected;
    - a record view, returned by FonDump.get() and by iterating a dump;
    - a nested view, returned by get_collection() and get_collection_array().

    Views never own native memory and keep their owner alive. A view raises
    StaleViewError after the value it refers to was changed or removed.
    Storing a view in another collection is an error; call clone() first.
    Storing an owned collection transfers it: the Python object is closed.

    Not thread-safe: use one collection tree from one thread at a time. The
    native library does not allow a tree to be mutated while another thread
    reads or closes it.
    """

    def __init__(self) -> None:
        handle: int = _n.fon_collection_create() or 0
        if not handle:
            raise MemoryError("fon_collection_create returned null")
        self._setup_owned(handle)

    # ---- construction and lifetime -----------------------------------------

    def _setup_owned(self, handle: int) -> None:
        self._handle: int = handle
        self._disposed: bool = False
        self._owned: bool = True
        self._moved: bool = False
        self._top: Any = None
        self._in_dump: bool = False
        self._is_record: bool = False
        self._rec_id: int = 0
        self._rec_gen: int = 0
        self._tree_gen: int = 0
        self._captured_tree: int = 0
        self._cached_version: int = 0
        self._version: int = 0
        self._tree_version: int = 0

    @classmethod
    def _adopt(cls, handle: int) -> "FonCollection":
        """Wrap a freshly created native handle that this object now owns."""
        collection: FonCollection = cls.__new__(cls)
        collection._setup_owned(handle)
        return collection

    @classmethod
    def _make_view(
        cls,
        handle: int,
        top: Any,
        in_dump: bool,
        record_id: int,
        is_record: bool,
    ) -> "FonCollection":
        view: FonCollection = cls.__new__(cls)
        view._handle = handle
        view._disposed = False
        view._owned = False
        view._top = top
        view._in_dump = in_dump
        view._is_record = is_record
        view._rec_id = record_id
        view._rec_gen = 0
        view._tree_gen = 0
        view._captured_tree = 0
        view._cached_version = 0
        view._capture()
        return view

    def _capture(self) -> None:
        """Record the generations and versions that this view is valid for."""
        top: Any = self._top
        if self._in_dump:
            gens: Optional[tuple] = top._gens(self._rec_id)
            if gens is None:
                raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _STALE_MESSAGE)
            self._rec_gen = gens[0]
            self._tree_gen = gens[1]
        else:
            self._captured_tree = top._tree_version
        self._cached_version = top._version

    def _resolve(self) -> int:
        """Validate this object and return its current native handle."""
        if self._owned:
            if self._disposed:
                raise RuntimeError(_CLOSED_MESSAGE)
            return self._handle
        top: Any = self._top
        if top._disposed:
            if top._moved:
                raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _TRANSFERRED_OWNER_MESSAGE)
            raise RuntimeError(_OWNER_MESSAGE)
        if top._version == self._cached_version:
            return self._handle
        if self._in_dump:
            gens: Optional[tuple] = top._gens(self._rec_id)
            if gens is None or gens[0] != self._rec_gen:
                raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _STALE_MESSAGE)
            if not self._is_record:
                if gens[1] != self._tree_gen:
                    raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _STALE_MESSAGE)
            else:
                handle: int = top._record_handle(self._rec_id)
                if not handle:
                    raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _STALE_MESSAGE)
                self._handle = handle
        elif top._tree_version != self._captured_tree:
            raise StaleViewError(_n.FON_ERROR_STALE_VIEW, _STALE_MESSAGE)
        self._cached_version = top._version
        return self._handle

    def _after_mutation(self) -> None:
        """Bump the versions of the tree this object belongs to after a successful write."""
        if self._owned:
            self._version += 1
            self._tree_version += 1
            return
        top: Any = self._top
        if self._in_dump:
            top._record_mutated(self._rec_id)
            if self._is_record:
                self._handle = top._record_handle(self._rec_id)
            self._capture()
            return
        top._version += 1
        top._tree_version += 1
        self._capture()

    def _transfer(self) -> None:
        """Hand this owned collection's native handle to a new owner."""
        self._disposed = True
        self._moved = True
        self._handle = 0

    @property
    def _owns(self) -> bool:
        """True while this object owns a live native handle (views never do)."""
        return self._owned and not self._disposed

    @property
    def _transferred(self) -> bool:
        """True once an owned collection has been handed to a container or closed."""
        return self._owned and self._disposed

    @staticmethod
    def _validate_child(child: Any, target: Any) -> None:
        """Check that child can be stored in target. Raises before any native call."""
        if not isinstance(child, FonCollection):
            raise TypeError(f"expected FonCollection, got {type(child).__name__}")
        if not child._owned:
            raise InvalidArgumentError(
                _n.FON_ERROR_INVALID_ARGUMENT,
                "a view cannot be stored in another collection or dump; call clone() first",
            )
        if child._disposed:
            raise RuntimeError("this FonCollection was already transferred or closed and must not be used")
        if child is target:
            raise InvalidArgumentError(_n.FON_ERROR_INVALID_ARGUMENT, "a collection cannot be stored in itself")
        if isinstance(target, FonCollection) and not target._owned and target._top is child:
            raise InvalidArgumentError(
                _n.FON_ERROR_INVALID_ARGUMENT,
                "a collection cannot be stored in a view of itself, that would create a cycle",
            )

    def _child_view(self, handle: int) -> "FonCollection":
        """Create a nested view of a child handle that belongs to this object's tree."""
        if self._owned:
            return FonCollection._make_view(handle, self, False, 0, False)
        return FonCollection._make_view(handle, self._top, self._in_dump, self._rec_id, False)

    def close(self) -> None:
        """Release the native memory of an owned collection. Views are unaffected by close()."""
        if self._owned and not self._disposed:
            handle: int = self._handle
            self._handle = 0
            self._disposed = True
            _n.fon_collection_free(handle)

    def __enter__(self) -> "FonCollection":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        if getattr(self, "_owned", False) and not getattr(self, "_disposed", True):
            handle: int = self._handle
            self._handle = 0
            self._disposed = True
            _n.fon_collection_free(handle)

    # ---- native call helpers -------------------------------------------------

    def _native_put(self, fn: Any, key: str, mode: int, *args: Any, transfers: Tuple["FonCollection", ...] = ()) -> None:
        handle: int = self._resolve()
        key_bytes: bytes = _n.encode_text(key)
        err: Any = _n._FonError()
        rc: int = fn(handle, key_bytes, len(key_bytes), *args, mode, byref(err))
        if rc == _n.FON_OK:
            for child in transfers:
                child._transfer()
        _n.check(rc, err)
        self._after_mutation()

    def _put_child(self, fn: Any, key: str, mode: int, child: "FonCollection") -> None:
        self._resolve()
        FonCollection._validate_child(child, self)
        self._native_put(fn, key, mode, child._handle, transfers=(child,))

    def _put_children(self, fn: Any, key: str, mode: int, children: List["FonCollection"]) -> None:
        self._resolve()
        seen: set = set()
        for child in children:
            FonCollection._validate_child(child, self)
            if id(child) in seen:
                raise InvalidArgumentError(
                    _n.FON_ERROR_INVALID_ARGUMENT,
                    "the same collection appears more than once in the array",
                )
            seen.add(id(child))
        handles: Any = (c_void_p * max(1, len(children)))(*[child._handle for child in children])
        self._native_put(fn, key, mode, handles, len(children), transfers=tuple(children))

    def _native_get_scalar(self, fn: Any, key: str, out: Any) -> Any:
        handle: int = self._resolve()
        key_bytes: bytes = _n.encode_text(key)
        err: Any = _n._FonError()
        rc: int = fn(handle, key_bytes, len(key_bytes), byref(out), byref(err))
        _n.check(rc, err)
        return out.value

    def _native_get_bytes(self, fn: Any, key: str) -> bytes:
        handle: int = self._resolve()
        return _n.read_bytes(fn, handle, _n.encode_text(key))

    def _native_get_array(self, fn: Any, key: str, typecode: str) -> Any:
        handle: int = self._resolve()
        return _n.read_array(fn, handle, typecode, _n.encode_text(key))

    def _native_get_child(self, key: str) -> "FonCollection":
        handle: int = self._resolve()
        key_bytes: bytes = _n.encode_text(key)
        err: Any = _n._FonError()
        child: int = _n.fon_collection_get_collection(handle, key_bytes, len(key_bytes), byref(err))
        child = _n.require_handle(child, err, _n.FON_ERROR_INVALID_ARGUMENT)
        return self._child_view(child)

    def _native_get_children(self, key: str) -> List["FonCollection"]:
        handle: int = self._resolve()
        handles: List[int] = _n.read_handles(
            _n.fon_collection_get_collection_array, handle, _n.encode_text(key)
        )
        return [self._child_view(item) for item in handles]

    # ---- size, keys and kinds ----------------------------------------------

    def __len__(self) -> int:
        handle: int = self._resolve()
        return int(_n.fon_collection_size(handle))

    def keys(self) -> List[str]:
        """Return the keys in insertion order."""
        handle: int = self._resolve()
        return [name for name, _ in _n.read_keys(handle)]

    def kind(self, key: str) -> Optional[FonKind]:
        """Return the kind of the value under key, or None when the key is absent."""
        handle: int = self._resolve()
        key_bytes: bytes = _n.encode_text(key)
        code: int = _n.fon_collection_kind_of(handle, key_bytes, len(key_bytes))
        if code < 0:
            return None
        return kind_from_code(code)

    def has(self, key: str) -> bool:
        """Return True when key is present with any type."""
        return self.kind(key) is not None

    def remove(self, key: str) -> bool:
        """Remove key. Returns False when the key was absent."""
        handle: int = self._resolve()
        key_bytes: bytes = _n.encode_text(key)
        removed: int = _n.fon_collection_remove(handle, key_bytes, len(key_bytes))
        if removed == 1:
            self._after_mutation()
            return True
        return False

    def clone(self) -> "FonCollection":
        """Return a new owned deep copy. Works on owned collections and on views."""
        handle: int = self._resolve()
        err: Any = _n._FonError()
        copy: int = _n.fon_collection_clone(handle, byref(err))
        copy = _n.require_handle(copy, err, _n.FON_ERROR_INVALID_ARGUMENT)
        return FonCollection._adopt(copy)

    # ---- add (key must not exist) -------------------------------------------

    def add_byte(self, key: str, value: int) -> None:
        """Add a u8 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_byte, key, _n.FON_PUT_ADD, _n.arg_u8(value))

    def add_short(self, key: str, value: int) -> None:
        """Add an i16 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_short, key, _n.FON_PUT_ADD, _n.arg_i16(value))

    def add_int(self, key: str, value: int) -> None:
        """Add an i32 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_int, key, _n.FON_PUT_ADD, _n.arg_i32(value))

    def add_uint(self, key: str, value: int) -> None:
        """Add a u32 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_uint, key, _n.FON_PUT_ADD, _n.arg_u32(value))

    def add_long(self, key: str, value: int) -> None:
        """Add an i64 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_long, key, _n.FON_PUT_ADD, _n.arg_i64(value))

    def add_ulong(self, key: str, value: int) -> None:
        """Add a u64 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_ulong, key, _n.FON_PUT_ADD, _n.arg_u64(value))

    def add_float(self, key: str, value: float) -> None:
        """Add an f32 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_float, key, _n.FON_PUT_ADD, _n.arg_f32(value))

    def add_double(self, key: str, value: float) -> None:
        """Add an f64 value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_double, key, _n.FON_PUT_ADD, _n.arg_f64(value))

    def add_bool(self, key: str, value: bool) -> None:
        """Add a boolean value. Raises AlreadyExistsError if the key exists."""
        self._native_put(_n.fon_collection_put_bool, key, _n.FON_PUT_ADD, _n.arg_bool(value))

    def add_string(self, key: str, value: str) -> None:
        """Add a string value. Raises AlreadyExistsError if the key exists."""
        payload: bytes = _n.encode_text(value)
        self._native_put(_n.fon_collection_put_string, key, _n.FON_PUT_ADD, payload, len(payload))

    def add_raw(self, key: str, value: bytes) -> None:
        """Add a raw binary value. Raises AlreadyExistsError if the key exists."""
        payload: bytes = _n.raw_bytes(value)
        self._native_put(_n.fon_collection_put_raw, key, _n.FON_PUT_ADD, payload, len(payload))

    def add_byte_array(self, key: str, values: List[int]) -> None:
        """Add a u8 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_BYTE, values)
        self._native_put(_n.fon_collection_put_byte_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_short_array(self, key: str, values: List[int]) -> None:
        """Add an i16 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_SHORT, values)
        self._native_put(_n.fon_collection_put_short_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_int_array(self, key: str, values: List[int]) -> None:
        """Add an i32 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_INT, values)
        self._native_put(_n.fon_collection_put_int_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_uint_array(self, key: str, values: List[int]) -> None:
        """Add a u32 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_UINT, values)
        self._native_put(_n.fon_collection_put_uint_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_long_array(self, key: str, values: List[int]) -> None:
        """Add an i64 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_LONG, values)
        self._native_put(_n.fon_collection_put_long_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_ulong_array(self, key: str, values: List[int]) -> None:
        """Add a u64 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_ULONG, values)
        self._native_put(_n.fon_collection_put_ulong_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_float_array(self, key: str, values: List[float]) -> None:
        """Add an f32 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_FLOAT, values)
        self._native_put(_n.fon_collection_put_float_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_double_array(self, key: str, values: List[float]) -> None:
        """Add an f64 array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_DOUBLE, values)
        self._native_put(_n.fon_collection_put_double_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_bool_array(self, key: str, values: List[bool]) -> None:
        """Add a boolean array. Raises AlreadyExistsError if the key exists."""
        data, count = _n.pack_array(_n.TC_BYTE, [1 if item else 0 for item in values])
        self._native_put(_n.fon_collection_put_bool_array, key, _n.FON_PUT_ADD, _n.buffer_address(data), count)

    def add_string_array(self, key: str, values: List[str]) -> None:
        """Add a string array. Raises AlreadyExistsError if the key exists."""
        lengths, payload, count = _n.pack_strings(values)
        self._native_put(_n.fon_collection_put_string_array, key, _n.FON_PUT_ADD, lengths, payload, count)

    def add_collection(self, key: str, child: "FonCollection") -> None:
        """
        Nest an owned collection under key. The child is transferred and must not be used afterwards.
        Raises AlreadyExistsError if the key exists; the child then stays usable.
        """
        self._put_child(_n.fon_collection_put_collection, key, _n.FON_PUT_ADD, child)

    def add_collection_array(self, key: str, children: List["FonCollection"]) -> None:
        """
        Nest an array of owned collections under key. All children are transferred on success.
        Raises AlreadyExistsError if the key exists; the children then stay usable.
        """
        self._put_children(_n.fon_collection_put_collection_array, key, _n.FON_PUT_ADD, list(children))

    # ---- set (upsert) -------------------------------------------------------

    def set_byte(self, key: str, value: int) -> None:
        """Set a u8 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_byte, key, _n.FON_PUT_UPSERT, _n.arg_u8(value))

    def set_short(self, key: str, value: int) -> None:
        """Set an i16 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_short, key, _n.FON_PUT_UPSERT, _n.arg_i16(value))

    def set_int(self, key: str, value: int) -> None:
        """Set an i32 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_int, key, _n.FON_PUT_UPSERT, _n.arg_i32(value))

    def set_uint(self, key: str, value: int) -> None:
        """Set a u32 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_uint, key, _n.FON_PUT_UPSERT, _n.arg_u32(value))

    def set_long(self, key: str, value: int) -> None:
        """Set an i64 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_long, key, _n.FON_PUT_UPSERT, _n.arg_i64(value))

    def set_ulong(self, key: str, value: int) -> None:
        """Set a u64 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_ulong, key, _n.FON_PUT_UPSERT, _n.arg_u64(value))

    def set_float(self, key: str, value: float) -> None:
        """Set an f32 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_float, key, _n.FON_PUT_UPSERT, _n.arg_f32(value))

    def set_double(self, key: str, value: float) -> None:
        """Set an f64 value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_double, key, _n.FON_PUT_UPSERT, _n.arg_f64(value))

    def set_bool(self, key: str, value: bool) -> None:
        """Set a boolean value, replacing any existing value under key."""
        self._native_put(_n.fon_collection_put_bool, key, _n.FON_PUT_UPSERT, _n.arg_bool(value))

    def set_string(self, key: str, value: str) -> None:
        """Set a string value, replacing any existing value under key."""
        payload: bytes = _n.encode_text(value)
        self._native_put(_n.fon_collection_put_string, key, _n.FON_PUT_UPSERT, payload, len(payload))

    def set_raw(self, key: str, value: bytes) -> None:
        """Set a raw binary value, replacing any existing value under key."""
        payload: bytes = _n.raw_bytes(value)
        self._native_put(_n.fon_collection_put_raw, key, _n.FON_PUT_UPSERT, payload, len(payload))

    def set_byte_array(self, key: str, values: List[int]) -> None:
        """Set a u8 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_BYTE, values)
        self._native_put(_n.fon_collection_put_byte_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_short_array(self, key: str, values: List[int]) -> None:
        """Set an i16 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_SHORT, values)
        self._native_put(_n.fon_collection_put_short_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_int_array(self, key: str, values: List[int]) -> None:
        """Set an i32 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_INT, values)
        self._native_put(_n.fon_collection_put_int_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_uint_array(self, key: str, values: List[int]) -> None:
        """Set a u32 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_UINT, values)
        self._native_put(_n.fon_collection_put_uint_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_long_array(self, key: str, values: List[int]) -> None:
        """Set an i64 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_LONG, values)
        self._native_put(_n.fon_collection_put_long_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_ulong_array(self, key: str, values: List[int]) -> None:
        """Set a u64 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_ULONG, values)
        self._native_put(_n.fon_collection_put_ulong_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_float_array(self, key: str, values: List[float]) -> None:
        """Set an f32 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_FLOAT, values)
        self._native_put(_n.fon_collection_put_float_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_double_array(self, key: str, values: List[float]) -> None:
        """Set an f64 array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_DOUBLE, values)
        self._native_put(_n.fon_collection_put_double_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_bool_array(self, key: str, values: List[bool]) -> None:
        """Set a boolean array, replacing any existing value under key."""
        data, count = _n.pack_array(_n.TC_BYTE, [1 if item else 0 for item in values])
        self._native_put(_n.fon_collection_put_bool_array, key, _n.FON_PUT_UPSERT, _n.buffer_address(data), count)

    def set_string_array(self, key: str, values: List[str]) -> None:
        """Set a string array, replacing any existing value under key."""
        lengths, payload, count = _n.pack_strings(values)
        self._native_put(_n.fon_collection_put_string_array, key, _n.FON_PUT_UPSERT, lengths, payload, count)

    def set_collection(self, key: str, child: "FonCollection") -> None:
        """
        Set an owned collection under key, replacing any existing value.
        The child is transferred and must not be used afterwards.
        """
        self._put_child(_n.fon_collection_put_collection, key, _n.FON_PUT_UPSERT, child)

    def set_collection_array(self, key: str, children: List["FonCollection"]) -> None:
        """
        Set an array of owned collections under key, replacing any existing value.
        All children are transferred on success.
        """
        self._put_children(_n.fon_collection_put_collection_array, key, _n.FON_PUT_UPSERT, list(children))

    # ---- get (typed read) ---------------------------------------------------

    def get_byte(self, key: str) -> int:
        """Get a u8 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_byte, key, c_uint8()))

    def get_short(self, key: str) -> int:
        """Get an i16 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_short, key, c_int16()))

    def get_int(self, key: str) -> int:
        """Get an i32 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_int, key, c_int32()))

    def get_uint(self, key: str) -> int:
        """Get a u32 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_uint, key, c_uint32()))

    def get_long(self, key: str) -> int:
        """Get an i64 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_long, key, c_int64()))

    def get_ulong(self, key: str) -> int:
        """Get a u64 value. Raises NotFoundError or TypeMismatchError."""
        return int(self._native_get_scalar(_n.fon_collection_get_ulong, key, c_uint64()))

    def get_float(self, key: str) -> float:
        """Get an f32 value. Raises NotFoundError or TypeMismatchError."""
        return float(self._native_get_scalar(_n.fon_collection_get_float, key, c_float()))

    def get_double(self, key: str) -> float:
        """Get an f64 value. Raises NotFoundError or TypeMismatchError."""
        return float(self._native_get_scalar(_n.fon_collection_get_double, key, c_double()))

    def get_bool(self, key: str) -> bool:
        """Get a boolean value. Raises NotFoundError or TypeMismatchError."""
        return bool(self._native_get_scalar(_n.fon_collection_get_bool, key, c_int32()))

    def get_string(self, key: str, buffer_size: Optional[int] = None) -> str:
        """
        Get a string value. The buffer_size parameter is kept for compatibility and ignored:
        the exact size is queried, so values of any length are returned whole.
        """
        return self._native_get_bytes(_n.fon_collection_get_string, key).decode("utf-8")

    def get_raw(self, key: str) -> bytes:
        """Get a raw binary value. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_bytes(_n.fon_collection_get_raw, key)

    def get_byte_array(self, key: str) -> List[int]:
        """Get a u8 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_byte_array, key, _n.TC_BYTE).tolist()

    def get_short_array(self, key: str) -> List[int]:
        """Get an i16 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_short_array, key, _n.TC_SHORT).tolist()

    def get_int_array(self, key: str) -> List[int]:
        """Get an i32 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_int_array, key, _n.TC_INT).tolist()

    def get_uint_array(self, key: str) -> List[int]:
        """Get a u32 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_uint_array, key, _n.TC_UINT).tolist()

    def get_long_array(self, key: str) -> List[int]:
        """Get an i64 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_long_array, key, _n.TC_LONG).tolist()

    def get_ulong_array(self, key: str) -> List[int]:
        """Get a u64 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_ulong_array, key, _n.TC_ULONG).tolist()

    def get_float_array(self, key: str) -> List[float]:
        """Get an f32 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_float_array, key, _n.TC_FLOAT).tolist()

    def get_double_array(self, key: str) -> List[float]:
        """Get an f64 array. Raises NotFoundError or TypeMismatchError."""
        return self._native_get_array(_n.fon_collection_get_double_array, key, _n.TC_DOUBLE).tolist()

    def get_bool_array(self, key: str) -> List[bool]:
        """Get a boolean array. Raises NotFoundError or TypeMismatchError."""
        values: List[int] = self._native_get_array(_n.fon_collection_get_bool_array, key, _n.TC_BYTE).tolist()
        return [item != 0 for item in values]

    def get_string_array(self, key: str) -> List[str]:
        """Get a string array. Raises NotFoundError or TypeMismatchError."""
        handle: int = self._resolve()
        return _n.read_strings(_n.fon_collection_get_string_array, handle, _n.encode_text(key))

    def get_collection(self, key: str) -> "FonCollection":
        """
        Get a nested view of the collection under key. The view keeps this object's tree alive
        and becomes stale after any change to the tree that contains it.
        """
        return self._native_get_child(key)

    def get_collection_array(self, key: str) -> List["FonCollection"]:
        """Get nested views of the collections in the array under key."""
        return self._native_get_children(key)

    # ---- mapping protocol ---------------------------------------------------

    def get(self, key: str) -> Any:
        """
        Get a value of any type, dispatching on its kind. Arrays become lists;
        nested collections become nested views. Raises NotFoundError when absent.
        """
        found: Optional[FonKind] = self.kind(key)
        if found is None:
            raise NotFoundError(_n.FON_ERROR_NOT_FOUND, f"key '{key}' not found")
        suffix: str = "collection" if found.type == "object" else found.type
        if found.is_array:
            suffix = suffix + "_array"
        getter: Any = getattr(self, "get_" + suffix)
        return getter(key)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if isinstance(value, FonCollection):
            self.set_collection(key, value)
        elif isinstance(value, bool):
            self.set_bool(key, value)
        elif isinstance(value, int):
            self.set_long(key, value)
        elif isinstance(value, float):
            self.set_double(key, value)
        elif isinstance(value, str):
            self.set_string(key, value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            self.set_raw(key, bytes(value))
        elif isinstance(value, list):
            self._set_inferred_list(key, value)
        else:
            raise TypeError(f"cannot store a value of type {type(value).__name__}")

    def _set_inferred_list(self, key: str, items: List[Any]) -> None:
        if not items:
            raise TypeError("cannot infer the array kind of an empty list; use set_<kind>_array")
        if all(isinstance(item, FonCollection) for item in items):
            self.set_collection_array(key, items)
        elif all(isinstance(item, bool) for item in items):
            self.set_bool_array(key, items)
        elif all(isinstance(item, str) for item in items):
            self.set_string_array(key, items)
        elif all(isinstance(item, int) and not isinstance(item, bool) for item in items):
            self.set_long_array(key, items)
        elif all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in items):
            self.set_double_array(key, items)
        else:
            raise TypeError("cannot infer one array kind for this list; use set_<kind>_array")

    def __delitem__(self, key: str) -> None:
        if not self.remove(key):
            raise NotFoundError(_n.FON_ERROR_NOT_FOUND, f"key '{key}' not found")

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return self.has(key)

    def __iter__(self) -> Any:
        return iter(self.keys())

    # ---- serialization ------------------------------------------------------

    def serialize(self) -> str:
        """Serialize this collection to a single FON line."""
        handle: int = self._resolve()
        return _n.take_output(_n.fon_serialize_collection, handle).decode("utf-8")

    @classmethod
    def deserialize(cls, line: str) -> "FonCollection":
        """Parse a single FON line and return a new owned collection."""
        data: bytes = _n.encode_text(line)
        err: Any = _n._FonError()
        handle: int = _n.fon_deserialize_collection(data, len(data), byref(err))
        handle = _n.require_handle(handle, err, _n.FON_ERROR_PARSE_FAILED)
        return cls._adopt(handle)

    def __repr__(self) -> str:
        try:
            return f"<FonCollection {self.serialize()!r}>"
        except Exception:
            return "<FonCollection>"
