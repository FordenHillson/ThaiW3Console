"""Bit packing helpers for SWF shape / tag records."""
from __future__ import annotations


class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.bit = 0
        self.cur = 0

    def flush(self) -> None:
        if self.bit:
            self.data.append(self.cur)
            self.bit = 0
            self.cur = 0

    def u(self, n: int, value: int) -> None:
        for i in range(n - 1, -1, -1):
            self.cur = (self.cur << 1) | ((value >> i) & 1)
            self.bit += 1
            if self.bit == 8:
                self.data.append(self.cur & 0xFF)
                self.bit = 0
                self.cur = 0

    def s(self, n: int, value: int) -> None:
        self.u(n, value & ((1 << n) - 1))

    def bytes(self) -> bytes:
        self.flush()
        return bytes(self.data)


def bits_needed(value: int) -> int:
    """Unsigned bit count for |value| as a signed magnitude (min 1 when non-zero)."""
    if value == 0:
        return 0
    v = abs(value)
    n = 1
    while (1 << (n - 1)) <= v:
        n += 1
        if n >= 32:
            break
    return n
