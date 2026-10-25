"""
Value kind introspection.
"""

from __future__ import annotations

from typing import Dict, NamedTuple

from ._native import FON_KIND_ARRAY


class FonKind(NamedTuple):
    """
    The kind of a stored value.

    type is one of: byte, short, int, uint, long, ulong, float, double, bool,
    string, raw, object (a nested collection). is_array tells whether the value
    is an array of that type.
    """

    type: str
    is_array: bool


_TYPE_NAMES: Dict[int, str] = {
    ord("e"): "byte",
    ord("t"): "short",
    ord("i"): "int",
    ord("u"): "uint",
    ord("l"): "long",
    ord("g"): "ulong",
    ord("f"): "float",
    ord("d"): "double",
    ord("b"): "bool",
    ord("s"): "string",
    ord("r"): "raw",
    ord("o"): "object",
}


def kind_from_code(code: int) -> FonKind:
    """Convert the native kind value (type char | FON_KIND_ARRAY) to a FonKind."""
    type_name: str = _TYPE_NAMES.get(code & 0xFF, "unknown")
    is_array: bool = (code & FON_KIND_ARRAY) != 0
    return FonKind(type_name, is_array)
