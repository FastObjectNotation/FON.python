# FON — Fast Object Notation

[![CI](https://github.com/FastObjectNotation/FON.python/actions/workflows/ci.yml/badge.svg)](https://github.com/FastObjectNotation/FON.python/actions/workflows/ci.yml)

FON is a fast, human-readable, line-oriented serialization format. A compact
alternative to JSON for record-style data. Each line is one record; values are
typed and can nest.

## Features

- **Compact, readable wire format** — `key=type:value` pairs, one record per line.
- **Typed values** — numeric/bool/string primitives, binary blobs, nested objects,
  and arrays of any of them.
- **Nested objects & arrays of objects**, with configurable maximum depth.
- **Parallel** dump serialization and deserialization.
- **Byte-oriented parsing** — BOM tolerant, reads straight from bytes.
- **Z85 binary encoding** for raw blobs.
- **No compiled extension** — loads a bundled shared library automatically; no build step needed when installing from PyPI.

## Format

Each line is one record: a comma-separated list of `key=type:value` pairs. A
`.fon` file is a sequence of records, indexed by line number (0-based).

```
name=s:"John",age=i:30,balance=d:1234.56
scores=i:[95,87,92],tags=s:["admin","user"]
user=o:{id=i:42,name=s:"Bob",addr=o:{city=s:"NY",zip=i:10001}}
items=o:[{id=i:1,qty=i:5},{id=i:2,qty=i:3}]
blob=r:"nm=QNzv..."
```

### Type codes

| Code | Type            | Example                       |
|------|-----------------|-------------------------------|
| `e`  | `u8`            | `count=e:255`                 |
| `t`  | `i16`           | `year=t:2024`                 |
| `i`  | `i32`           | `id=i:42`                     |
| `u`  | `u32`           | `flags=u:12345`               |
| `l`  | `i64`           | `ts=l:1700000000`             |
| `g`  | `u64`           | `big=g:18446744073709551615`  |
| `f`  | `f32`           | `ratio=f:3.14`                |
| `d`  | `f64`           | `pi=d:3.141592653589793`      |
| `s`  | `String`        | `name=s:"Hello"`              |
| `b`  | `bool`          | `active=b:1`                  |
| `r`  | `RawData` (Z85) | `data=r:"nm=QNzv"`            |
| `o`  | `FonCollection` | `user=o:{id=i:1}`             |

## Install

```bash
pip install FastObjectNotation
```

> **Note:** The wheel bundles a pre-built shared library for the target platform.
> See "Build" below if you need to build from source.

## Usage

### A single collection

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
print(restored.get_int("id"))      # 42
print(restored.get_string("name")) # Test Item
print(restored.get_double("price"))# 99.99
print(restored.get_bool("active")) # True
```

### Many records (FonDump)

```python
from fon import FonCollection, FonDump

dump = FonDump()
for i in range(1000):
    col = FonCollection()
    col.add_int("id", i)
    col.add_string("label", f"row_{i}")
    dump.add(i, col)         # ownership of col transfers to dump here

text = dump.serialize()

restored = FonDump.deserialize(text)
entry = restored.get(0)
print(entry.get_string("label"))  # row_0
```

### Version

```python
from fon import native_version
print(native_version())  # 0.3.0
```

## Build

Requires Rust (cargo) and Python 3.9+.

```bash
git clone --recurse-submodules https://github.com/FastObjectNotation/FON.python.git
cd FON.python

# Build the native library
cargo build --release --manifest-path native/Cargo.toml

# Run the tests
python -m unittest discover -s tests -v
```

The cdylib lands in `native/target/release/fon_native.dll` (Windows),
`libfon_native.so` (Linux), or `libfon_native.dylib` (macOS).
The Python package discovers it automatically relative to the `fon/` directory.
