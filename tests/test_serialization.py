"""
Serialization options and file errors (design section 6, items 7 and 8).
"""

import os
import pathlib
import tempfile
import unittest

from fon import FON_ERROR_FILE_NOT_FOUND, FonCollection, FonDump, FonError, deserialize_dump_from_file


def make_dump(count: int) -> FonDump:
    dump = FonDump()
    for record_id in range(count):
        col = FonCollection()
        col.add_long("id", record_id)
        col.add_string("label", f"row {record_id}")
        col.add_double_array("scores", [record_id * 0.5, -1.25])
        dump.add(record_id, col)
    return dump


class TestMaxThreads(unittest.TestCase):
    def test_max_threads_one_and_two_serialize_identically_to_zero(self) -> None:
        dump: FonDump = make_dump(2000)
        expected: str = dump.serialize(0)
        self.assertEqual(dump.serialize(1), expected)
        self.assertEqual(dump.serialize(2), expected)

    def test_max_threads_one_and_two_deserialize_identically_to_zero(self) -> None:
        text: str = make_dump(2000).serialize()
        expected: list = FonDump.deserialize(text, 0).ids()
        self.assertEqual(FonDump.deserialize(text, 1).ids(), expected)
        self.assertEqual(FonDump.deserialize(text, 2).ids(), expected)
        self.assertEqual(len(FonDump.deserialize(text, 1)), 2000)

    def test_max_threads_for_file_round_trip_matches_zero(self) -> None:
        dump: FonDump = make_dump(500)
        with tempfile.TemporaryDirectory() as folder:
            path_zero: str = os.path.join(folder, "zero.fon")
            path_two: str = os.path.join(folder, "two.fon")
            dump.serialize_to_file(path_zero, 0)
            dump.serialize_to_file(path_two, 2)
            with open(path_zero, "rb") as zero_file, open(path_two, "rb") as two_file:
                self.assertEqual(zero_file.read(), two_file.read())
            restored: FonDump = deserialize_dump_from_file(path_two, 1)
            self.assertEqual(len(restored), 500)


class TestFileRoundTrip(unittest.TestCase):
    def test_file_round_trip_accepts_pathlib_paths(self) -> None:
        dump: FonDump = make_dump(3)
        with tempfile.TemporaryDirectory() as folder:
            path: pathlib.Path = pathlib.Path(folder) / "dump.fon"
            dump.serialize_to_file(path)
            restored: FonDump = FonDump.deserialize_from_file(path)
            self.assertEqual(restored.ids(), [0, 1, 2])
            self.assertEqual(restored.get(2).get_string("label"), "row 2")


class TestMissingFile(unittest.TestCase):
    def test_deserializing_missing_file_raises_file_not_found(self) -> None:
        missing: str = os.path.join(tempfile.gettempdir(), "fon_missing_file_does_not_exist_12345.fon")
        with self.assertRaises(FonError) as context:
            deserialize_dump_from_file(missing)
        self.assertEqual(context.exception.code, FON_ERROR_FILE_NOT_FOUND)

    def test_class_method_missing_file_raises_file_not_found(self) -> None:
        missing: str = os.path.join(tempfile.gettempdir(), "fon_missing_file_does_not_exist_67890.fon")
        with self.assertRaises(FonError) as context:
            FonDump.deserialize_from_file(missing)
        self.assertEqual(context.exception.code, FON_ERROR_FILE_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
