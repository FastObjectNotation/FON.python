"""
FonDump: an id to collection store that owns a native dump handle.
"""

from __future__ import annotations

from ctypes import byref, c_uint32
from typing import Any, Iterator, List, Optional, Tuple

from . import _native as _n
from ._collection import FonCollection
from ._errors import NotFoundError


class FonDump:
    """
    An id to collection store. Owns a native dump.

    add(), set() and replace() transfer the collection: after a successful call
    the FonCollection passed in is closed and must not be used. Records returned
    by get(), indexing and iteration are views that keep this dump alive. A view
    raises StaleViewError when its record is removed or replaced, or when the
    record was changed after the view was taken.

    Not thread-safe: use one dump from one thread at a time. The native library
    does not allow a dump to be mutated while another thread reads or closes it.
    """

    def __init__(self) -> None:
        handle: int = _n.fon_dump_create() or 0
        if not handle:
            raise MemoryError("fon_dump_create returned null")
        self._setup(handle)

    def _setup(self, handle: int) -> None:
        self._handle: int = handle
        self._disposed: bool = False
        self._moved: bool = False
        self._version: int = 0

    @classmethod
    def _adopt(cls, handle: int) -> "FonDump":
        dump: FonDump = cls.__new__(cls)
        dump._setup(handle)
        return dump

    def close(self) -> None:
        """Release the native dump. Views of this dump raise RuntimeError afterwards."""
        if not self._disposed:
            handle: int = self._handle
            self._handle = 0
            self._disposed = True
            _n.fon_dump_free(handle)

    def __enter__(self) -> "FonDump":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        if not getattr(self, "_disposed", True):
            handle: int = self._handle
            self._handle = 0
            self._disposed = True
            _n.fon_dump_free(handle)

    def _ptr(self) -> int:
        if self._disposed:
            raise RuntimeError("this FonDump has been closed and must not be used")
        return self._handle

    # ---- internal services for views -----------------------------------------

    def _gens(self, record_id: int) -> Optional[Tuple[int, int]]:
        """Return (record_gen, tree_gen) for a live record, or None when it is absent."""
        handle: int = self._ptr()
        record_gen: Any = c_uint32(0)
        tree_gen: Any = c_uint32(0)
        live: int = _n.fon_dump_gens(handle, record_id, byref(record_gen), byref(tree_gen))
        if live == 0:
            return None
        return int(record_gen.value), int(tree_gen.value)

    def _record_handle(self, record_id: int) -> int:
        """Return the current borrowed handle of a record, or 0 when it is absent."""
        handle: int = self._ptr()
        return _n.fon_dump_get(handle, record_id) or 0

    def _record_mutated(self, record_id: int) -> None:
        """Called after a write inside a record: marks the record's tree as changed."""
        handle: int = self._ptr()
        _n.fon_dump_touch(handle, record_id)
        self._version += 1

    # ---- size and enumeration ------------------------------------------------

    def __len__(self) -> int:
        handle: int = self._ptr()
        return int(_n.fon_dump_size(handle))

    def ids(self) -> List[int]:
        """Return the live ids in ascending order."""
        handle: int = self._ptr()
        return _n.read_array(_n.fon_dump_ids, handle, _n.TC_ULONG, None).tolist()

    def has(self, id: int) -> bool:
        """Return True when a record with this id exists."""
        record_id: Optional[int] = _n.find_id(id)
        if record_id is None:
            return False
        return self._record_handle(record_id) != 0

    def get(self, id: int) -> Optional[FonCollection]:
        """Return a record view for id, or None when the id is absent."""
        handle: int = self._ptr()
        record_id: Optional[int] = _n.find_id(id)
        if record_id is None:
            return None
        record: int = _n.fon_dump_get(handle, record_id) or 0
        if not record:
            return None
        return FonCollection._make_view(record, self, True, record_id, True)

    def items(self) -> Iterator[Tuple[int, FonCollection]]:
        """Yield (id, record view) pairs in ascending id order."""
        for record_id in self.ids():
            view: Optional[FonCollection] = self.get(record_id)
            if view is not None:
                yield record_id, view

    def __iter__(self) -> Iterator[int]:
        return iter(self.ids())

    def __getitem__(self, id: int) -> FonCollection:
        view: Optional[FonCollection] = self.get(id)
        if view is None:
            raise NotFoundError(_n.FON_ERROR_NOT_FOUND, f"record {id} not found")
        return view

    def __setitem__(self, id: int, collection: FonCollection) -> None:
        self.set(id, collection)

    def __delitem__(self, id: int) -> None:
        if not self.remove(id):
            raise NotFoundError(_n.FON_ERROR_NOT_FOUND, f"record {id} not found")

    def __contains__(self, id: object) -> bool:
        if not isinstance(id, int):
            return False
        return self.has(id)

    # ---- mutation ----------------------------------------------------------------

    def _put_record(self, mode: int, id: int, collection: FonCollection) -> None:
        handle: int = self._ptr()
        record_id: int = _n.uint64_id(id)
        FonCollection._validate_child(collection, self)
        err: Any = _n._FonError()
        rc: int = _n.fon_dump_put(handle, record_id, collection._handle, mode, byref(err))
        if rc == _n.FON_OK:
            collection._transfer()
        _n.check(rc, err)
        self._version += 1

    def add(self, id: int, collection: FonCollection) -> None:
        """
        Add a collection under id. Raises AlreadyExistsError if id exists.
        The collection is transferred on success.
        """
        self._put_record(_n.FON_PUT_ADD, id, collection)

    def set(self, id: int, collection: FonCollection) -> None:
        """Set the collection under id, replacing any record with that id. The collection is transferred."""
        self._put_record(_n.FON_PUT_UPSERT, id, collection)

    def replace(self, id: int, collection: FonCollection) -> None:
        """Replace the existing record under id. Raises NotFoundError if id is absent. The collection is transferred."""
        self._put_record(_n.FON_PUT_SET, id, collection)

    def remove(self, id: int) -> bool:
        """Remove the record under id. Returns False when the id was absent."""
        handle: int = self._ptr()
        record_id: Optional[int] = _n.find_id(id)
        if record_id is None:
            return False
        removed: bool = _n.fon_dump_remove(handle, record_id) == 1
        self._version += 1
        return removed

    def remove_many(self, ids: Any) -> int:
        """Remove several records. Absent and duplicate ids are ignored. Returns the number removed."""
        handle: int = self._ptr()
        values: Any = [_n.uint64_id(item) for item in ids]
        data, count = _n.pack_array(_n.TC_ULONG, values)
        removed: int = int(_n.fon_dump_remove_many(handle, _n.buffer_address(data), count))
        self._version += 1
        return removed

    # ---- serialization -----------------------------------------------------------

    def serialize(self, max_threads: int = 0) -> str:
        """Serialize this dump to a multi-line FON string."""
        handle: int = self._ptr()
        return _n.take_output(_n.fon_serialize_dump, handle, max_threads).decode("utf-8")

    def serialize_to_file(self, path: Any, max_threads: int = 0) -> None:
        """
        Write this dump to a file.

        Parameters
        ----------
        path:
            File path (str or os.PathLike).
        max_threads:
            Maximum worker threads for this call; 0 uses all cores.
        """
        handle: int = self._ptr()
        path_data: bytes = _n.path_bytes(path)
        err: Any = _n._FonError()
        rc: int = _n.fon_serialize_to_file(handle, path_data, len(path_data), max_threads, byref(err))
        _n.check(rc, err)

    @classmethod
    def deserialize(cls, text: str, max_threads: int = 0) -> "FonDump":
        """Parse a multi-line FON string and return a new owned dump."""
        data: bytes = _n.encode_text(text)
        err: Any = _n._FonError()
        handle: int = _n.fon_deserialize_dump(data, len(data), max_threads, byref(err))
        handle = _n.require_handle(handle, err, _n.FON_ERROR_PARSE_FAILED)
        return cls._adopt(handle)

    @classmethod
    def deserialize_from_file(cls, path: Any, max_threads: int = 0) -> "FonDump":
        """Read a FON dump file and return a new owned dump. Raises FonError with FON_ERROR_FILE_NOT_FOUND if missing."""
        path_data: bytes = _n.path_bytes(path)
        err: Any = _n._FonError()
        handle: int = _n.fon_deserialize_from_file(path_data, len(path_data), max_threads, byref(err))
        handle = _n.require_handle(handle, err, _n.FON_ERROR_FILE_NOT_FOUND)
        return cls._adopt(handle)

    def __repr__(self) -> str:
        if self._disposed:
            return "<FonDump (closed)>"
        return f"<FonDump size={len(self)}>"


def deserialize_dump_from_file(path: Any, max_threads: int = 0) -> FonDump:
    """
    Read a FON dump file from disk and return a new owned FonDump.

    Parameters
    ----------
    path:
        File path (str or os.PathLike).
    max_threads:
        Maximum worker threads for this call; 0 uses all cores.
    """
    return FonDump.deserialize_from_file(path, max_threads)
