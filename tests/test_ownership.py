"""
Ownership (design section 6, item 6).

A view cannot be stored in another container, clone() makes a storable copy, a
successful put transfers the collection, a failed put leaves the child owned and
usable, and cycles or repeated children are rejected.
"""

import unittest
from unittest import mock

from fon import AlreadyExistsError, FonCollection, FonDump, InvalidArgumentError
from fon import _native


def make_child(value: int) -> FonCollection:
    child = FonCollection()
    child.add_long("v", value)
    return child


class TestViewsCannotBeStored(unittest.TestCase):
    def test_nested_view_as_field_value_is_argument_error(self) -> None:
        parent = FonCollection()
        parent.add_collection("c", make_child(1))
        view = parent.get_collection("c")
        target = FonCollection()
        with self.assertRaises(InvalidArgumentError) as context:
            target.add_collection("again", view)
        self.assertEqual(context.exception.code, 4)
        self.assertIn("clone()", context.exception.message)

    def test_clone_of_view_can_be_stored(self) -> None:
        parent = FonCollection()
        parent.add_collection("c", make_child(1))
        target = FonCollection()
        target.add_collection("again", parent.get_collection("c").clone())
        self.assertEqual(target.get_collection("again").get_long("v"), 1)

    def test_record_view_put_into_dump_is_argument_error(self) -> None:
        dump = FonDump()
        dump.add(0, make_child(1))
        other = FonDump()
        with self.assertRaises(InvalidArgumentError) as context:
            other.add(0, dump.get(0))
        self.assertEqual(context.exception.code, 4)
        self.assertEqual(dump.get(0).get_long("v"), 1)

    def test_view_stored_in_array_is_argument_error(self) -> None:
        parent = FonCollection()
        parent.add_collection("c", make_child(1))
        target = FonCollection()
        with self.assertRaises(InvalidArgumentError) as context:
            target.add_collection_array("rows", [parent.get_collection("c")])
        self.assertEqual(context.exception.code, 4)
        self.assertFalse(target.has("rows"))


class TestTransfer(unittest.TestCase):
    def test_successful_put_makes_passed_collection_unusable(self) -> None:
        parent = FonCollection()
        child = make_child(1)
        parent.add_collection("c", child)
        with self.assertRaises(RuntimeError):
            child.add_int("again", 2)
        with self.assertRaises(RuntimeError):
            child.get_long("v")

    def test_dump_add_transfers_collection(self) -> None:
        dump = FonDump()
        child = make_child(4)
        dump.add(0, child)
        with self.assertRaises(RuntimeError):
            child.get_long("v")
        self.assertEqual(dump.get(0).get_long("v"), 4)

    def test_collection_array_transfers_every_child(self) -> None:
        first: FonCollection = make_child(1)
        second: FonCollection = make_child(2)
        parent = FonCollection()
        parent.add_collection_array("rows", [first, second])
        with self.assertRaises(RuntimeError):
            first.get_long("v")
        with self.assertRaises(RuntimeError):
            second.get_long("v")
        self.assertEqual([row.get_long("v") for row in parent.get_collection_array("rows")], [1, 2])

    def test_child_is_transferred_even_if_the_call_is_interrupted_after_the_native_put(self) -> None:
        parent = FonCollection()
        child = make_child(3)
        with mock.patch.object(FonCollection, "_after_mutation", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                parent.add_collection("c", child)
        with self.assertRaises(RuntimeError):
            child.get_long("v")
        self.assertEqual(parent.get_collection("c").get_long("v"), 3)

    def test_dump_child_is_transferred_even_if_the_call_is_interrupted_after_the_native_put(self) -> None:
        dump = FonDump()
        child = make_child(5)
        with mock.patch.object(_native, "check", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                dump.add(0, child)
        with self.assertRaises(RuntimeError):
            child.get_long("v")
        self.assertEqual(dump.get(0).get_long("v"), 5)


class TestCloseReleasesHandleOnce(unittest.TestCase):
    def test_handle_is_marked_disposed_before_it_is_freed(self) -> None:
        col = make_child(1)
        seen: list = []
        real_free = _native.fon_collection_free

        def free_spy(handle: int) -> None:
            seen.append(col._disposed)
            real_free(handle)

        with mock.patch.object(_native, "fon_collection_free", side_effect=free_spy):
            col.close()
            col.close()
        self.assertEqual(seen, [True])

    def test_dump_handle_is_marked_disposed_before_it_is_freed(self) -> None:
        dump = FonDump()
        seen: list = []
        real_free = _native.fon_dump_free

        def free_spy(handle: int) -> None:
            seen.append(dump._disposed)
            real_free(handle)

        with mock.patch.object(_native, "fon_dump_free", side_effect=free_spy):
            dump.close()
            dump.close()
        self.assertEqual(seen, [True])


class TestFailedPutLeavesChildOwned(unittest.TestCase):
    def test_add_on_existing_key_keeps_child_usable(self) -> None:
        parent = FonCollection()
        parent.add_int("c", 1)
        child = make_child(7)
        with self.assertRaises(AlreadyExistsError):
            parent.add_collection("c", child)
        self.assertEqual(child.get_long("v"), 7)

    def test_child_of_failed_put_can_still_be_stored_with_set(self) -> None:
        parent = FonCollection()
        parent.add_int("c", 1)
        child = make_child(8)
        with self.assertRaises(AlreadyExistsError):
            parent.add_collection("c", child)
        parent.set_collection("c", child)
        with self.assertRaises(RuntimeError):
            child.get_long("v")
        self.assertEqual(parent.get_collection("c").get_long("v"), 8)

    def test_dump_add_on_existing_id_keeps_child_usable(self) -> None:
        dump = FonDump()
        dump.add(0, make_child(1))
        child = make_child(2)
        with self.assertRaises(AlreadyExistsError):
            dump.add(0, child)
        self.assertEqual(child.get_long("v"), 2)
        dump.set(0, child)
        self.assertEqual(dump.get(0).get_long("v"), 2)


class TestCycles(unittest.TestCase):
    def test_inserting_root_into_its_own_nested_view_is_rejected(self) -> None:
        root = FonCollection()
        root.add_collection("c", make_child(1))
        nested = root.get_collection("c")
        with self.assertRaises(InvalidArgumentError) as context:
            nested.add_collection("back", root)
        self.assertEqual(context.exception.code, 4)
        self.assertEqual(root.get_collection("c").get_long("v"), 1)

    def test_inserting_collection_into_itself_is_rejected(self) -> None:
        col = FonCollection()
        with self.assertRaises(InvalidArgumentError) as context:
            col.add_collection("self", col)
        self.assertEqual(context.exception.code, 4)
        col.add_int("ok", 1)
        self.assertEqual(col.get_int("ok"), 1)

    def test_same_child_twice_in_one_array_is_rejected(self) -> None:
        child = make_child(1)
        parent = FonCollection()
        with self.assertRaises(InvalidArgumentError) as context:
            parent.add_collection_array("rows", [child, child])
        self.assertEqual(context.exception.code, 4)
        self.assertFalse(parent.has("rows"))
        self.assertEqual(child.get_long("v"), 1)
        parent.add_collection("single", child)
        self.assertEqual(parent.get_collection("single").get_long("v"), 1)

    def test_same_child_twice_in_set_array_is_rejected(self) -> None:
        child = make_child(1)
        parent = FonCollection()
        with self.assertRaises(InvalidArgumentError) as context:
            parent.set_collection_array("rows", [child, child])
        self.assertEqual(context.exception.code, 4)
        self.assertEqual(child.get_long("v"), 1)


if __name__ == "__main__":
    unittest.main()
