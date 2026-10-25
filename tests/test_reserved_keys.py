"""
Reserved key characters (design section 6, item 9, decision D15).

A key containing one of = " { } [ ] CR LF cannot be written back to a parseable
line, so every put with such a key is rejected as an argument error. A child
collection passed to a rejected put stays owned and usable by the caller.
"""

import unittest

from fon import FonCollection, FonError, InvalidArgumentError


RESERVED_KEYS: list = ["a=b", 'a"b', "a{b", "a}b", "a[b", "a]b", "a\nb", "a\rb"]


def make_child() -> FonCollection:
    child = FonCollection()
    child.add_long("v", 7)
    return child


class TestReservedKeysAreRejected(unittest.TestCase):
    def test_scalar_add_raises_invalid_argument(self) -> None:
        col = FonCollection()
        for key in RESERVED_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(InvalidArgumentError) as context:
                    col.add_int(key, 1)
                self.assertEqual(context.exception.code, 4)
                self.assertIn("reserved", context.exception.message)
        self.assertEqual(len(col), 0)

    def test_error_is_value_error_and_fon_error(self) -> None:
        col = FonCollection()
        with self.assertRaises(ValueError):
            col.set_string("a=b", "x")
        with self.assertRaises(FonError):
            col.set_string("a=b", "x")

    def test_indexer_assignment_raises_and_stores_nothing(self) -> None:
        col = FonCollection()
        for key in RESERVED_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(InvalidArgumentError):
                    col[key] = "value"
        self.assertEqual(col.keys(), [])

    def test_array_put_with_reserved_key_raises(self) -> None:
        col = FonCollection()
        with self.assertRaises(InvalidArgumentError):
            col.add_int_array("x]y", [1, 2, 3])
        with self.assertRaises(InvalidArgumentError):
            col.set_string_array("x]y", ["a", "b"])
        self.assertEqual(len(col), 0)

    def test_valid_key_still_accepted_after_rejections(self) -> None:
        col = FonCollection()
        for key in RESERVED_KEYS:
            with self.assertRaises(InvalidArgumentError):
                col.add_int(key, 1)
        col.add_int("plain key with spaces", 2)
        self.assertEqual(col.get_int("plain key with spaces"), 2)


class TestRejectedChildStaysOwned(unittest.TestCase):
    def test_child_of_rejected_add_collection_is_still_usable(self) -> None:
        parent = FonCollection()
        child = make_child()
        for key in RESERVED_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(InvalidArgumentError):
                    parent.add_collection(key, child)
                self.assertEqual(child.get_long("v"), 7)
        self.assertEqual(len(parent), 0)

    def test_child_of_rejected_put_can_be_stored_under_valid_key(self) -> None:
        parent = FonCollection()
        child = make_child()
        with self.assertRaises(InvalidArgumentError):
            parent.set_collection("x{y", child)
        parent.set_collection("ok", child)
        self.assertEqual(parent.get_collection("ok").get_long("v"), 7)

    def test_child_of_rejected_collection_array_is_still_usable(self) -> None:
        parent = FonCollection()
        first = make_child()
        second = make_child()
        with self.assertRaises(InvalidArgumentError):
            parent.add_collection_array("bad]key", [first, second])
        self.assertEqual(first.get_long("v"), 7)
        self.assertEqual(second.get_long("v"), 7)
        parent.add_collection_array("good", [first, second])
        self.assertEqual(len(parent.get_collection_array("good")), 2)


if __name__ == "__main__":
    unittest.main()
