"""
Enumeration (design section 6, item 3).

Collection keys come back in insertion order with their kinds. Dump ids come
back ascending after sparse adds and removals. Enumerating a large dump stays
linear.
"""

import time
import unittest
from typing import List, Tuple

from fon import FonCollection, FonDump, FonKind


class TestCollectionKeys(unittest.TestCase):
    def test_keys_in_insertion_order_with_kinds(self) -> None:
        col = FonCollection()
        col.add_long("zeta", 1)
        col.add_string("alpha", "a")
        col.add_int_array("mid", [1, 2])
        col.add_collection("child", FonCollection())
        col.add_raw("blob", b"\x01")
        self.assertEqual(col.keys(), ["zeta", "alpha", "mid", "child", "blob"])
        self.assertEqual(col.kind("zeta"), FonKind("long", False))
        self.assertEqual(col.kind("alpha"), FonKind("string", False))
        self.assertEqual(col.kind("mid"), FonKind("int", True))
        self.assertEqual(col.kind("child"), FonKind("object", False))
        self.assertEqual(col.kind("blob"), FonKind("raw", False))

    def test_keys_after_removal_keep_order(self) -> None:
        col = FonCollection()
        for name in ("a", "b", "c", "d"):
            col.add_int(name, 0)
        col.remove("b")
        self.assertEqual(col.keys(), ["a", "c", "d"])

    def test_keys_of_empty_collection(self) -> None:
        self.assertEqual(FonCollection().keys(), [])

    def test_keys_of_deserialized_collection_keep_kinds(self) -> None:
        col = FonCollection()
        col.add_double("price", 2.5)
        col.add_bool_array("flags", [True])
        restored: FonCollection = FonCollection.deserialize(col.serialize())
        self.assertEqual(restored.keys(), ["price", "flags"])
        self.assertEqual(restored.kind("price"), FonKind("double", False))
        self.assertEqual(restored.kind("flags"), FonKind("bool", True))


class TestDumpIds(unittest.TestCase):
    def test_ids_ascending_after_sparse_adds_and_removals(self) -> None:
        dump = FonDump()
        for record_id in (5, 1, 9, 3, 7, 1000000):
            col = FonCollection()
            col.add_long("id", record_id)
            dump.add(record_id, col)
        self.assertEqual(dump.ids(), [1, 3, 5, 7, 9, 1000000])
        dump.remove(3)
        dump.remove(9)
        self.assertEqual(dump.ids(), [1, 5, 7, 1000000])

    def test_ids_of_empty_dump(self) -> None:
        self.assertEqual(FonDump().ids(), [])

    def test_ids_are_uint64_values(self) -> None:
        dump = FonDump()
        big_id: int = 2 ** 64 - 1
        dump.add(big_id, FonCollection())
        dump.add(0, FonCollection())
        self.assertEqual(dump.ids(), [0, big_id])

    def test_iteration_yields_ascending_ids_with_views(self) -> None:
        dump = FonDump()
        for record_id in (4, 2, 8):
            col = FonCollection()
            col.add_long("v", record_id * 10)
            dump.add(record_id, col)
        pairs: List[Tuple[int, int]] = [(record_id, view.get_long("v")) for record_id, view in dump.items()]
        self.assertEqual(pairs, [(2, 20), (4, 40), (8, 80)])
        self.assertEqual(list(dump), [2, 4, 8])


class TestLargeDumpEnumeration(unittest.TestCase):
    def test_enumerating_100000_records_is_fast(self) -> None:
        template = FonCollection()
        template.add_long("value", 7)
        line: str = template.serialize()
        text: str = "\n".join([line] * 100000)

        dump: FonDump = FonDump.deserialize(text)
        self.assertEqual(len(dump), 100000)

        started: float = time.perf_counter()
        total: int = 0
        for record_id, view in dump.items():
            total += view.get_long("value")
        elapsed: float = time.perf_counter() - started

        self.assertEqual(total, 700000)
        self.assertLess(elapsed, 2.0, f"enumeration took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
