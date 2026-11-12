"""
Strict behaviour: malformed text is an error, an empty line is an empty record,
and a value that cannot be stored as given is rejected instead of being altered.
"""

import unittest

from fon import FON_ERROR_PARSE_FAILED, FonCollection, FonDump, FonError, InvalidArgumentError, set_max_depth


MALFORMED_LINES: list = [
    "a=b:[[]]",
    "a=i:12abc",
    "a=i:+",
    "a=b:false",
    "a=i:1,junk",
    "a=i:1,a=i:2",
    "a=i:1,",
    "a=i:[1,,2]",
    'a=s:"\\q"',
]


class TestMalformedTextIsRejected(unittest.TestCase):
    def test_malformed_record_raises_a_parse_error(self) -> None:
        for line in MALFORMED_LINES:
            with self.subTest(line=line):
                with self.assertRaises(FonError) as caught:
                    FonCollection.deserialize(line)
                self.assertEqual(caught.exception.code, FON_ERROR_PARSE_FAILED)

    def test_dump_parse_error_names_the_line(self) -> None:
        for threads in (1, 2, 0):
            with self.subTest(threads=threads):
                with self.assertRaises(FonError) as caught:
                    FonDump.deserialize("a=i:1\na=b:[[]]\nc=i:3\n", threads)
                self.assertEqual(caught.exception.code, FON_ERROR_PARSE_FAILED)
                self.assertTrue(caught.exception.message.startswith("line 2: "), caught.exception.message)


class TestEmptyRecords(unittest.TestCase):
    def test_empty_record_survives_save_and_load(self) -> None:
        dump = FonDump()
        first = FonCollection()
        first.add_int("x", 1)
        third = FonCollection()
        third.add_int("x", 3)
        dump.add(0, first)
        dump.add(1, FonCollection())
        dump.add(2, third)

        text: str = dump.serialize()
        self.assertEqual(text, "x=i:1\n\nx=i:3\n")

        loaded = FonDump.deserialize(text)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(len(loaded.get(1)), 0)
        self.assertEqual(loaded.get(2).get_int("x"), 3)
        loaded.close()
        dump.close()


class TestValuesAreStoredAsGivenOrNotAtAll(unittest.TestCase):
    def test_bool_setters_take_only_bool(self) -> None:
        col = FonCollection()
        for value in ("false", 0, 1, None, "x", []):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    col.add_bool("b", value)
                with self.assertRaises(TypeError):
                    col.set_bool("b", value)
        with self.assertRaises(TypeError):
            col.add_bool_array("list", [True, "false"])
        with self.assertRaises(TypeError):
            col.set_bool_array("list", [1, 0])
        self.assertEqual(len(col), 0)

        col.add_bool("b", False)
        col.add_bool_array("list", [True, False])
        self.assertIs(col.get_bool("b"), False)
        self.assertEqual(col.get_bool_array("list"), [True, False])
        col.close()

    def test_float32_overflow_raises(self) -> None:
        col = FonCollection()
        with self.assertRaises(OverflowError):
            col.add_float("f", 1e39)
        with self.assertRaises(OverflowError):
            col.set_float("f", -1e39)
        with self.assertRaises(OverflowError):
            col.add_float_array("list", [1.0, 3.5e38])
        self.assertEqual(len(col), 0)

        col.add_float("max", 3.4028234663852886e38)
        col.add_float("inf", float("inf"))
        col.add_float_array("list", [1.5, float("-inf")])
        self.assertEqual(col.get_float("max"), 3.4028234663852886e38)
        self.assertEqual(col.get_float("inf"), float("inf"))
        self.assertEqual(col.get_float_array("list"), [1.5, float("-inf")])
        col.close()

    def test_lone_surrogate_is_rejected(self) -> None:
        col = FonCollection()
        with self.assertRaises((UnicodeEncodeError, InvalidArgumentError)):
            col.add_string("s", "a\ud800b")
        with self.assertRaises((UnicodeEncodeError, InvalidArgumentError)):
            col.add_int("k\udc00", 1)
        self.assertEqual(len(col), 0)
        col.close()


class TestIntegersOutsideInt32(unittest.TestCase):
    def test_thread_counts_are_saturated_not_wrapped(self) -> None:
        dump = FonDump()
        record = FonCollection()
        record.add_int("n", 1)
        dump.add(0, record)
        for threads in (2 ** 63, -(2 ** 63), 2 ** 31, 2 ** 32 + 1):
            with self.subTest(threads=threads):
                text: str = dump.serialize(threads)
                loaded = FonDump.deserialize(text, threads)
                self.assertEqual(len(loaded), 1)
                loaded.close()
        dump.close()

    def test_max_depth_is_saturated_not_wrapped(self) -> None:
        # 2**32 + 1 used to wrap to 1, which rejects every nested object.
        set_max_depth(2 ** 32 + 1)
        try:
            nested = FonCollection.deserialize("a=o:{b=o:{c=i:1}}")
            self.assertEqual(nested.get_collection("a").get_collection("b").get_int("c"), 1)
            nested.close()
        finally:
            set_max_depth(64)

    def test_remove_many_ignores_ids_that_cannot_exist(self) -> None:
        dump = FonDump()
        dump.add(0, FonCollection())
        dump.add(1, FonCollection())
        self.assertEqual(dump.remove_many([0, -1, 2 ** 64, 7]), 1)
        self.assertEqual(len(dump), 1)
        dump.close()


class TestCycles(unittest.TestCase):
    def test_collection_cannot_be_stored_inside_its_own_nested_collection(self) -> None:
        root = FonCollection()
        middle = FonCollection()
        middle.add_collection("leaf", FonCollection())
        root.add_collection("middle", middle)
        leaf = root.get_collection("middle").get_collection("leaf")

        with self.assertRaises(FonError):
            leaf.add_collection("back", root)
        with self.assertRaises(FonError):
            leaf.add_collection_array("backs", [root])
        self.assertEqual(root.serialize(), "middle=o:{leaf=o:{}}")
        root.close()


if __name__ == "__main__":
    unittest.main()
