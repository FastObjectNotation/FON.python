"""
Views (design section 6, item 5).

A record view survives its own edits. Views go stale when the value they refer
to changes, and never crash. Views keep their owner alive, and raise
RuntimeError once the owner has been closed.
"""

import gc
import unittest

from fon import FonCollection, FonDump, StaleViewError


def force_gc() -> None:
    gc.collect()
    gc.collect()


class TestRecordViews(unittest.TestCase):
    def make_dump(self) -> FonDump:
        dump = FonDump()
        for record_id in range(3):
            col = FonCollection()
            col.add_long("w", record_id + 1)
            col.add_collection("child", self.make_child(record_id))
            dump.add(record_id, col)
        return dump

    def make_child(self, value: int) -> FonCollection:
        child = FonCollection()
        child.add_long("x", value)
        return child

    def test_record_view_survives_repeated_set_on_itself(self) -> None:
        dump = self.make_dump()
        record = dump.get(0)
        for _ in range(3):
            record.set_long("w", record.get_long("w") * 2)
        self.assertEqual(record.get_long("w"), 8)
        self.assertEqual(dump.get(0).get_long("w"), 8)

    def test_record_view_stale_after_its_record_is_removed(self) -> None:
        dump = self.make_dump()
        record = dump.get(1)
        dump.remove(1)
        with self.assertRaises(StaleViewError):
            record.get_long("w")

    def test_record_view_stale_after_its_record_is_replaced(self) -> None:
        dump = self.make_dump()
        record = dump.get(1)
        replacement = FonCollection()
        replacement.add_long("w", 50)
        dump.replace(1, replacement)
        with self.assertRaises(StaleViewError):
            record.get_long("w")

    def test_view_of_another_id_is_unaffected(self) -> None:
        dump = self.make_dump()
        other = dump.get(2)
        dump.remove(0)
        dump.remove(1)
        self.assertEqual(other.get_long("w"), 3)

    def test_record_view_follows_other_mutations_in_the_dump(self) -> None:
        dump = self.make_dump()
        record = dump.get(0)
        newcomer = FonCollection()
        newcomer.add_long("w", 99)
        dump.add(10, newcomer)
        self.assertEqual(record.get_long("w"), 1)
        record.set_long("w", 5)
        self.assertEqual(record.get_long("w"), 5)


class TestNestedViews(unittest.TestCase):
    def make_dump(self) -> FonDump:
        dump = FonDump()
        col = FonCollection()
        col.add_long("w", 1)
        first = FonCollection()
        first.add_long("x", 1)
        second = FonCollection()
        second.add_long("x", 2)
        col.add_collection("a", first)
        col.add_collection("b", second)
        dump.add(0, col)
        return dump

    def test_nested_view_stale_after_field_change_in_record(self) -> None:
        dump = self.make_dump()
        record = dump.get(0)
        child = record.get_collection("a")
        record.set_long("w", 2)
        with self.assertRaises(StaleViewError):
            child.get_long("x")

    def test_dangling_child_overwritten_with_scalar_is_stale_not_a_crash(self) -> None:
        dump = self.make_dump()
        record = dump.get(0)
        child = record.get_collection("a")
        record.set_long("a", 5)
        with self.assertRaises(StaleViewError):
            child.get_long("x")
        with self.assertRaises(StaleViewError):
            child.serialize()
        self.assertEqual(record.get_long("a"), 5)

    def test_mutating_through_nested_view_keeps_it_valid_and_stales_siblings(self) -> None:
        dump = self.make_dump()
        record = dump.get(0)
        first = record.get_collection("a")
        second = record.get_collection("b")
        first.set_long("x", 10)
        self.assertEqual(first.get_long("x"), 10)
        with self.assertRaises(StaleViewError):
            second.get_long("x")
        self.assertEqual(dump.get(0).get_collection("a").get_long("x"), 10)

    def test_nested_view_of_owned_collection_stale_after_owner_mutated(self) -> None:
        root = FonCollection()
        child = FonCollection()
        child.add_long("x", 1)
        root.add_collection("c", child)
        nested = root.get_collection("c")
        root.set_long("other", 2)
        with self.assertRaises(StaleViewError):
            nested.get_long("x")

    def test_nested_view_of_owned_collection_valid_after_its_own_mutation(self) -> None:
        root = FonCollection()
        child = FonCollection()
        child.add_long("x", 1)
        root.add_collection("c", child)
        nested = root.get_collection("c")
        nested.set_long("x", 3)
        self.assertEqual(nested.get_long("x"), 3)
        self.assertEqual(root.get_collection("c").get_long("x"), 3)

    def test_nested_views_of_nested_views_follow_the_same_rules(self) -> None:
        root = FonCollection()
        middle = FonCollection()
        leaf = FonCollection()
        leaf.add_long("v", 1)
        middle.add_collection("leaf", leaf)
        root.add_collection("middle", middle)
        deep = root.get_collection("middle").get_collection("leaf")
        self.assertEqual(deep.get_long("v"), 1)
        deep.set_long("v", 2)
        self.assertEqual(deep.get_long("v"), 2)
        root.set_long("touch", 1)
        with self.assertRaises(StaleViewError):
            deep.get_long("v")


class TestClosedOwners(unittest.TestCase):
    def test_nested_view_after_owner_closed_raises_runtime_error(self) -> None:
        root = FonCollection()
        child = FonCollection()
        child.add_long("x", 1)
        root.add_collection("c", child)
        nested = root.get_collection("c")
        root.close()
        with self.assertRaises(RuntimeError):
            nested.get_long("x")

    def test_record_view_after_dump_closed_raises_runtime_error(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_long("x", 1)
        dump.add(0, col)
        record = dump.get(0)
        dump.close()
        with self.assertRaises(RuntimeError):
            record.get_long("x")

    def test_nested_view_of_record_after_dump_closed_raises_runtime_error(self) -> None:
        dump = FonDump()
        col = FonCollection()
        child = FonCollection()
        child.add_long("x", 1)
        col.add_collection("c", child)
        dump.add(0, col)
        nested = dump.get(0).get_collection("c")
        dump.close()
        with self.assertRaises(RuntimeError):
            nested.get_long("x")


class TestTransferredOwners(unittest.TestCase):
    def test_view_of_transferred_root_is_stale(self) -> None:
        inner = FonCollection()
        leaf = FonCollection()
        leaf.add_long("x", 1)
        inner.add_collection("k", leaf)
        view = inner.get_collection("k")
        FonCollection().add_collection("i", inner)
        with self.assertRaises(StaleViewError):
            view.get_long("x")

    def test_view_of_closed_root_raises_runtime_error(self) -> None:
        inner = FonCollection()
        leaf = FonCollection()
        leaf.add_long("x", 1)
        inner.add_collection("k", leaf)
        view = inner.get_collection("k")
        inner.close()
        with self.assertRaises(RuntimeError):
            view.get_long("x")


class TestViewsKeepOwnerAlive(unittest.TestCase):
    def test_record_view_keeps_dump_alive(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_string("name", "kept")
        dump.add(0, col)
        record = dump.get(0)
        del dump
        force_gc()
        self.assertEqual(record.get_string("name"), "kept")

    def test_nested_view_keeps_dump_alive(self) -> None:
        dump = FonDump()
        col = FonCollection()
        child = FonCollection()
        child.add_string("name", "deep")
        col.add_collection("c", child)
        dump.add(0, col)
        nested = dump.get(0).get_collection("c")
        del dump
        force_gc()
        self.assertEqual(nested.get_string("name"), "deep")

    def test_nested_view_keeps_owned_root_alive(self) -> None:
        root = FonCollection()
        child = FonCollection()
        child.add_string("name", "root kept")
        root.add_collection("c", child)
        nested = root.get_collection("c")
        del root
        force_gc()
        self.assertEqual(nested.get_string("name"), "root kept")

    def test_clone_of_view_is_owned_and_independent(self) -> None:
        dump = FonDump()
        col = FonCollection()
        col.add_long("x", 1)
        dump.add(0, col)
        copy: FonCollection = dump.get(0).clone()
        dump.get(0).set_long("x", 2)
        self.assertEqual(copy.get_long("x"), 1)
        self.assertEqual(dump.get(0).get_long("x"), 2)


if __name__ == "__main__":
    unittest.main()
