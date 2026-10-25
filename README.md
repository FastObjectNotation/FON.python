# FON — Fast Object Notation

[![CI](https://github.com/FastObjectNotation/FON.python/actions/workflows/ci.yml/badge.svg)](https://github.com/FastObjectNotation/FON.python/actions/workflows/ci.yml)

A fast, human-readable, line-oriented serialization format — a compact alternative to JSON for record-style data; each line is one record; values are typed and can nest.

## Features

- **Compact, readable wire format**: `key=type:value` pairs, one record per line.
- **Typed values**: integers of every width, floats, booleans, strings, binary blobs, nested objects, and arrays of each kind except blobs.
- **Nested objects and arrays of objects**, with a configurable maximum nesting depth.
- **Editable records**: add, set and remove fields; add, set, replace and remove records in a dump.
- **Safe views**: records and nested values read from a dump keep their owner alive, and stale data raises `StaleViewError` instead of being read.
- **Parallel serialization and parsing** of dumps, with a thread limit per call.
- **Z85 encoding** for binary blobs.
- **Bundled library**: each wheel includes the compiled library, so installing needs no build step.

## Format

Each line is one record: a comma-separated list of `key=type:value` pairs. A `.fon` file is a sequence of records, indexed by line number (0-based).

```
name=s:"John",age=i:30,balance=d:1234.56
scores=i:[95,87,92],tags=s:["admin","user"]
user=o:{id=i:42,name=s:"Bob",addr=o:{city=s:"NY",zip=i:10001}}
items=o:[{id=i:1,qty=i:5},{id=i:2,qty=i:3}]
blob=r:"?MsJX"
```

Arrays put square brackets after the type code. The `o` code marks a nested object (braces) or an array of nested objects (square brackets).

### Type codes

| Code | Python type | Example |
|------|-------------|---------|
| `e` | `int`, 0 to 255 | `count=e:255` |
| `t` | `int`, -32768 to 32767 | `year=t:2024` |
| `i` | `int`, 32-bit signed | `id=i:42` |
| `u` | `int`, 0 to 4294967295 | `flags=u:12345` |
| `l` | `int`, 64-bit signed | `ts=l:1700000000` |
| `g` | `int`, 0 to 18446744073709551615 | `big=g:18446744073709551615` |
| `f` | `float`, 32-bit | `ratio=f:3.14` |
| `d` | `float`, 64-bit | `pi=d:3.141592653589793` |
| `s` | `str` | `name=s:"Hello"` |
| `b` | `bool` | `active=b:1` |
| `r` | `bytes`, stored as Z85 text | `data=r:"?MsJX"` |
| `o` | `FonCollection` | `user=o:{id=i:1}` |

## Install

Each release provides a wheel for each supported platform. Install the wheel that matches yours:

```bash
pip install path/to/fastobjectnotation-0.4.0-<platform>.whl
```

The import name is `fon`. Requires Python 3.9 or later.

> **Note:** The wheel bundles a prebuilt shared library for its platform. To build the library from source, see [Build and test](#build-and-test).

## Usage

### A single record

```python
from fon import FonCollection

col = FonCollection()
col.add_int("id", 42)
col.add_string("name", "Test Item")
col.add_double("price", 99.99)
col.add_bool("active", True)

line = col.serialize()
# id=i:42,name=s:"Test Item",price=d:99.99,active=b:1

restored = FonCollection.deserialize(line)
print(restored.get_int("id"))        # 42
print(restored.get_string("name"))   # Test Item
print(restored.get_double("price"))  # 99.99
print(restored.get_bool("active"))   # True
```

### Many records

```python
from fon import FonCollection, FonDump

dump = FonDump()
for i in range(1000):
    col = FonCollection()
    col.add_int("id", i)
    col.add_string("label", f"row_{i}")
    dump.add(i, col)  # col is moved into the dump and must not be used again

text = dump.serialize()

restored = FonDump.deserialize(text)
entry = restored.get(0)
print(entry.get_string("label"))  # row_0
```

### Nested objects and arrays of objects

```python
from fon import FonCollection

customer = FonCollection()
customer.add_string("name", "Ann")

item1 = FonCollection()
item1.add_int("sku", 1)
item2 = FonCollection()
item2.add_int("sku", 2)

order = FonCollection()
order.add_collection("customer", customer)            # customer is moved into order
order.add_collection_array("items", [item1, item2])   # item1 and item2 are moved too

line = order.serialize()
# customer=o:{name=s:"Ann"},items=o:[{sku=i:1},{sku=i:2}]

restored = FonCollection.deserialize(line)
print(restored.get_collection("customer").get_string("name"))  # Ann
for item in restored.get_collection_array("items"):
    print(item.get_int("sku"))  # 1, then 2
```

### Editing records

```python
from fon import FonCollection

col = FonCollection.deserialize('name=s:"Ann",age=i:30,tags=s:["admin"]')
col.set_int("age", 31)           # set replaces the value; the type may change
col.set_string("name", "Anna")
col.add_bool("active", True)     # add raises AlreadyExistsError if the key exists
col["score"] = 9.5               # assignment infers the kind: double
print(col.remove("tags"))        # True; False when the key was absent
print(col.serialize())           # name=s:"Anna",age=i:31,active=b:1,score=d:9.5
```

Records in a dump are edited the same way, by id:

```python
from fon import FonCollection, FonDump

dump = FonDump()
dump.add(10, FonCollection.deserialize("n=i:1"))           # add: the id must be new
dump.set(11, FonCollection.deserialize("n=i:2"))           # set: insert or replace
dump.replace(11, FonCollection.deserialize("n=i:3"))       # replace: the id must exist
print(dump.remove(10))                                     # True
print(dump.remove_many([11, 99]))                          # 1; absent ids are ignored
```

Ids stay fixed while the dump is in memory. Serializing writes the remaining records in ascending id order, one line each, so reading the text back numbers them from 0:

```python
from fon import FonDump

dump = FonDump.deserialize("a=i:1\nb=i:2\nc=i:3")
dump.remove(1)
print(dump.ids())                                    # [0, 2]
print(FonDump.deserialize(dump.serialize()).ids())   # [0, 1]
```

### Binary data and parse options

```python
import fon
from fon import FonCollection

col = FonCollection()
col.add_raw("key", b"\xde\xad\xbe\xef")
line = col.serialize()
# key=r:"?MsJX"

restored = FonCollection.deserialize(line)
print(restored.get_raw("key"))  # b'\xde\xad\xbe\xef'

fon.set_raw_unpack(True)  # decode blobs while parsing; default False
fon.set_max_depth(32)     # reject nesting deeper than 32; default 64
```

`get_raw` returns the bytes whether or not raw unpacking is enabled. `set_raw_unpack` and `set_max_depth` apply to every later parse in the process.

The `max_threads` argument of `serialize`, `serialize_to_file`, `deserialize` and `deserialize_from_file` limits the worker threads for that call. `0` uses all cores.

## Memory and lifetime

A FON object is one of three kinds:

- **Owned collections** come from `FonCollection()`, `clone()` or `FonCollection.deserialize()`. They own their memory until `close()` is called or a `with` block ends. If neither happens, the memory is released when Python collects the object.
- **Dumps** come from `FonDump()`, `FonDump.deserialize()` or `deserialize_dump_from_file()`. They follow the same rules.
- **Views** never own memory. `dump.get(id)`, `dump[id]` and `dump.items()` return record views; `get_collection()` and `get_collection_array()` return nested views.

**Views keep their owner alive.** A view holds a reference to the dump or owned collection it came from, so the data stays valid while the view is in use, even after the variable that held the owner is gone.

**Stale views.** A view raises `StaleViewError` when the value it refers to has changed:

- A record view goes stale when its record is removed or replaced. Field edits made through the record view itself do not make it stale.
- A nested view goes stale after a change to its record, unless the change was made through that same view.
- A nested view of an owned collection goes stale after any change to that collection, unless the change was made through that same view.

**Closed owners.** Using a view after its dump or owned collection was closed raises `RuntimeError`. Using a closed owned collection or dump raises `RuntimeError` too.

**Ownership transfer.** Adding a collection to another collection or to a dump moves it: the Python object is closed, and using it afterwards raises `RuntimeError`. Only owned collections can be added. Adding a view raises `InvalidArgumentError`; call `clone()` on the view first. A collection cannot be added to itself, to a view of itself, or twice in one array. When the call fails, for example with `AlreadyExistsError`, nothing is moved and the collection stays usable.

**Copies.** `clone()` returns an independent owned deep copy of any collection, owned or view. Changing the copy does not change the original.

**Threads.** Use one dump or collection tree from one thread at a time.

## API

### FonCollection

| Member | Description |
|--------|-------------|
| `FonCollection()` | New empty owned collection. |
| `FonCollection.deserialize(line)` | Parse one line into a new owned collection. Raises `FonError` on malformed text. |
| `add_<kind>(key, value)` | Add a value. Raises `AlreadyExistsError` if the key exists. |
| `set_<kind>(key, value)` | Set a value, replacing any value of any kind under the key. |
| `get_<kind>(key)` | Typed read. Raises `NotFoundError` if the key is absent and `TypeMismatchError` if the kind differs. |
| `remove(key)` | Remove a key. Returns `bool`. |
| `has(key)` | `True` when the key is present. |
| `kind(key)` | `FonKind(type, is_array)` for the key, or `None`. |
| `keys()` | Keys in insertion order. |
| `get(key)` | Read any kind dynamically. Arrays become lists; nested collections become views. |
| `clone()` | Independent owned deep copy. |
| `serialize()` | The collection as one FON line. |
| `close()` | Release an owned collection. Has no effect on a view. |
| `len(col)`, `key in col`, `iter(col)` | Key count, key test, and iteration over keys. |
| `col[key]` | Same as `get(key)`. |
| `col[key] = value` | Same as `set` with inferred kind (see below). |
| `del col[key]` | Same as `remove`, but raises `NotFoundError` if the key is absent. |

The `<kind>` names are `byte`, `short`, `int`, `uint`, `long`, `ulong`, `float`, `double`, `bool`, `string`, `raw`, `byte_array`, `short_array`, `int_array`, `uint_array`, `long_array`, `ulong_array`, `float_array`, `double_array`, `bool_array`, `string_array`, `collection` and `collection_array`.

- `raw` takes and returns `bytes`.
- Each `*_array` kind takes and returns a `list`.
- `collection` takes an owned collection, which is moved on success. `get_collection` returns a nested view.
- `collection_array` takes a list of owned collections, which are moved on success. `get_collection_array` returns a list of nested views.
- `get_string(key, buffer_size=None)` accepts `buffer_size` for compatibility and ignores it.

**Inferred kinds for `col[key] = value`:** `bool` stores `bool`; `int` stores `long`; `float` stores `double`; `str` stores `string`; `bytes`, `bytearray` and `memoryview` store `raw`; `FonCollection` stores `collection`. A non-empty list of one kind stores the matching array kind, and a list mixing `int` and `float` stores `double_array`. Anything else, including an empty list, raises `TypeError`.

`kind(key)` returns a `FonKind` named tuple with `type` set to one of `byte`, `short`, `int`, `uint`, `long`, `ulong`, `float`, `double`, `bool`, `string`, `raw` or `object` (a nested collection), and `is_array` set to a `bool`.

### FonDump

| Member | Description |
|--------|-------------|
| `FonDump()` | New empty dump. |
| `FonDump.deserialize(text, max_threads=0)` | Parse a multi-line string into a new dump. |
| `FonDump.deserialize_from_file(path, max_threads=0)` | Read a dump file into a new dump. Raises `FonError` with code 1 if the file is missing. |
| `add(id, collection)` | Add a record. Raises `AlreadyExistsError` if the id exists. Moves the collection. |
| `set(id, collection)` | Insert or replace the record under the id. Moves the collection. |
| `replace(id, collection)` | Replace an existing record. Raises `NotFoundError` if the id is absent. Moves the collection. |
| `remove(id)` | Remove a record. Returns `bool`. |
| `remove_many(ids)` | Remove several records. Returns the number removed. |
| `has(id)` | `True` when the id is present. |
| `ids()` | Live ids in ascending order. |
| `get(id)` | Record view, or `None` when the id is absent. |
| `dump[id]` | Record view. Raises `NotFoundError` if the id is absent. |
| `dump[id] = collection` | Same as `set`. |
| `del dump[id]` | Same as `remove`, but raises `NotFoundError` if the id is absent. |
| `items()` | `(id, view)` pairs in ascending id order. |
| `len(dump)`, `id in dump`, `iter(dump)` | Record count, id test, and iteration over ids. |
| `serialize(max_threads=0)` | The dump as a multi-line string. |
| `serialize_to_file(path, max_threads=0)` | Write the dump to a file. |
| `close()` | Release the dump. Its views raise `RuntimeError` afterwards. |

### Module-level functions

| Function | Description |
|----------|-------------|
| `native_version()` | Version string of the bundled library. |
| `set_raw_unpack(enable)` | Decode blobs while parsing. Default `False`. |
| `set_max_depth(depth)` | Maximum nesting depth accepted when parsing. Default 64; values below 1 are treated as 1. |
| `deserialize_dump_from_file(path, max_threads=0)` | Same as `FonDump.deserialize_from_file`. |

### Errors

| Class | Raised when |
|-------|-------------|
| `FonError` | Any other failure, such as malformed text or a file that cannot be written. It has `code` and `message` attributes. |
| `NotFoundError` | A key or id is absent. Also a `KeyError`. |
| `TypeMismatchError` | A key holds a value of another kind. Also a `TypeError`. |
| `AlreadyExistsError` | An add targets an existing key or id. |
| `StaleViewError` | A view refers to a value that was changed or removed. |
| `InvalidArgumentError` | An argument is rejected, such as a key with a reserved character or a view passed where an owned collection is required. Also a `ValueError`. |

Using a closed or moved object raises the built-in `RuntimeError`, not one of the classes above.

## Build and test

Building from source needs a Rust toolchain with `cargo`, and Python 3.9 or later.

```bash
git clone --recurse-submodules https://github.com/FastObjectNotation/FON.python.git
cd FON.python

# Build the native library
cargo build --release --manifest-path native/Cargo.toml

# Run the tests
python -m unittest discover -s tests -v
```

The build writes `native/target/release/fon_native.dll` (Windows), `libfon_native.so` (Linux) or `libfon_native.dylib` (macOS). The package looks for the library in that folder first, then next to the `fon/` package. The `--recurse-submodules` flag fetches the core sources that the native build needs.
