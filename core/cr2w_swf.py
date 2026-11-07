"""Minimal CR2W helpers for editing compressed SWF inside .redswf (from ThaiW3Setup logo)."""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

HEADER_CRC_SEED = 0xDEADBEEF
HEADER_SIZE = 160


@dataclass
class Cr2wExport:
    index: int
    cls: str
    offset: int
    size: int
    props_end: int


@dataclass
class Cr2w:
    names: list[str]
    tables: list[tuple[int, int, int]]
    exports: list[Cr2wExport]


def read_cr2w(data: bytes) -> Cr2w:
    if data[:4] != b"CR2W":
        raise ValueError("not a CR2W file")
    tables = [struct.unpack_from("<III", data, 40 + i * 12) for i in range(10)]
    str_off, str_len, _ = tables[0]
    strings = data[str_off:str_off + str_len]
    names = []
    for i in range(tables[1][1]):
        o = struct.unpack_from("<I", data, tables[1][0] + i * 8)[0]
        names.append(strings[o:strings.index(b"\0", o)].decode("latin-1"))
    exports = []
    for i in range(tables[4][1]):
        cls, _flags, _parent, size, offset = struct.unpack_from("<HHIII", data, tables[4][0] + i * 24)
        p = offset + 1
        while True:
            name = struct.unpack_from("<H", data, p)[0]
            if name == 0:
                p += 2
                break
            ln = struct.unpack_from("<I", data, p + 4)[0]
            p += 4 + ln
        exports.append(Cr2wExport(i, names[cls], offset, size, p))
    return Cr2w(names, tables, exports)


def fix_crcs(data: bytearray, cr2w: Cr2w, changed: set[int]) -> None:
    table_off, count, _ = cr2w.tables[4]
    for exp in cr2w.exports:
        if exp.index in changed:
            struct.pack_into(
                "<I",
                data,
                table_off + exp.index * 24 + 20,
                zlib.crc32(data[exp.offset:exp.offset + exp.size]),
            )
    struct.pack_into("<I", data, 40 + 4 * 12 + 8, zlib.crc32(data[table_off:table_off + count * 24]))
    struct.pack_into("<I", data, 32, HEADER_CRC_SEED)
    struct.pack_into("<I", data, 32, zlib.crc32(data[:HEADER_SIZE]))
