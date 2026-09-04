"""IAR startup initialized-data stream decoder and size-optimal encoder."""

from __future__ import annotations

from dataclasses import dataclass
import struct

IMAGE_RUNTIME_BASE = 0x08001000
RAM_BASE = 0x20000000
ZERO_FILL_SIGNATURE = bytes.fromhex("00 20 01 e0 01 c1 12 1f 00 2a fb d1 70 47")


@dataclass(frozen=True)
class Descriptor:
    offset: int
    source_runtime: int
    destination: int
    output_length: int
    function_runtime: int

    @property
    def source_offset(self) -> int:
        return self.source_runtime - IMAGE_RUNTIME_BASE


def descriptors(blob: bytes) -> list[Descriptor]:
    found: list[Descriptor] = []
    for offset in range(0, len(blob) - 15, 4):
        source, destination, length, function = struct.unpack_from("<IIII", blob, offset)
        if not (RAM_BASE <= destination < RAM_BASE + 0x20000 and 0 < length < 0x10000):
            continue
        if not (IMAGE_RUNTIME_BASE <= function < IMAGE_RUNTIME_BASE + len(blob)):
            continue
        if source and not (IMAGE_RUNTIME_BASE <= source <= IMAGE_RUNTIME_BASE + len(blob)):
            continue
        found.append(Descriptor(offset, source, destination, length, function))
    return found


def find_initialized_data_descriptor(blob: bytes) -> Descriptor:
    matches = [d for d in descriptors(blob) if d.destination == RAM_BASE and d.source_runtime]
    if len(matches) != 1:
        raise ValueError(f"expected one IAR initialized-data descriptor, found {len(matches)}")
    return matches[0]


def read_descriptor(blob: bytes, offset: int) -> Descriptor:
    return Descriptor(offset, *struct.unpack_from("<IIII", blob, offset))


def decode(stream: bytes, output_length: int) -> tuple[bytes, int]:
    source = 0
    output = bytearray()
    while len(output) < output_length:
        if source >= len(stream):
            raise ValueError("truncated IAR stream")
        token = stream[source]
        source += 1
        literal_code = token & 7
        if literal_code == 0:
            literal_code = stream[source]
            source += 1
        run_code = token >> 4
        if run_code == 0:
            run_code = stream[source]
            source += 1
        literal_length = literal_code - 1
        if literal_length < 0 or source + literal_length > len(stream):
            raise ValueError("invalid literal in IAR stream")
        output += stream[source : source + literal_length]
        source += literal_length
        if token & 8:
            distance = stream[source]
            source += 1
            if distance == 0 or distance > len(output):
                raise ValueError("invalid back-reference in IAR stream")
            for _ in range(run_code + 2):
                output.append(output[-distance])
        else:
            output += b"\0" * run_code
    if len(output) != output_length:
        raise ValueError("IAR decoder exceeded the expected output length")
    return bytes(output), source


def _emit(literals: bytes, run_length: int, distance: int | None) -> bytes:
    literal_value = len(literals) + 1
    literal_nibble = literal_value if literal_value <= 7 else 0
    encoded_run = run_length if distance is None else run_length - 2
    run_nibble = encoded_run if 1 <= encoded_run <= 15 else 0
    token = (run_nibble << 4) | literal_nibble | (8 if distance is not None else 0)
    result = bytearray([token])
    if literal_nibble == 0:
        result.append(literal_value)
    if run_nibble == 0:
        result.append(encoded_run)
    result += literals
    if distance is not None:
        result.append(distance)
    return bytes(result)


def encode(data: bytes) -> bytes:
    size = len(data)
    max_match = [0] * size
    match_distance = [0] * size
    max_zero = [0] * size
    zero_count = 0
    for pos in range(size - 1, -1, -1):
        zero_count = min(255, zero_count + 1) if data[pos] == 0 else 0
        max_zero[pos] = zero_count
    for distance in range(1, 256):
        next_length = 0
        for pos in range(size - 1, distance - 1, -1):
            if data[pos] == data[pos - distance]:
                next_length = min(257, next_length + 1)
                if next_length > max_match[pos]:
                    max_match[pos] = next_length
                    match_distance[pos] = distance
            else:
                next_length = 0
    infinity = 1 << 60
    cost = [infinity] * (size + 1)
    cost[size] = 0
    choice: list[tuple[int, int, int | None] | None] = [None] * (size + 1)
    best_run: list[tuple[int, int, int | None] | None] = [None] * (size + 1)
    for pos in range(size - 1, -1, -1):
        run_best = infinity
        run_choice: tuple[int, int | None] | None = None
        for length in range(1, max_zero[pos] + 1):
            candidate = (0 if length <= 15 else 1) + cost[pos + length]
            if candidate < run_best:
                run_best, run_choice = candidate, (length, None)
        for length in range(2, min(257, max_match[pos]) + 1):
            encoded = length - 2
            candidate = (0 if 1 <= encoded <= 15 else 1) + 1 + cost[pos + length]
            if candidate < run_best:
                run_best, run_choice = candidate, (length, match_distance[pos])
        if run_choice:
            best_run[pos] = (run_best, run_choice[0], run_choice[1])
        for literal_length in range(min(254, size - pos) + 1):
            after = pos + literal_length
            literal_cost = literal_length + (1 if literal_length >= 7 else 0)
            run = best_run[after]
            if run and 1 + literal_cost + run[0] < cost[pos]:
                cost[pos] = 1 + literal_cost + run[0]
                choice[pos] = (literal_length, run[1], run[2])
            if literal_length and 1 + literal_cost + 1 + cost[after] < cost[pos]:
                cost[pos] = 1 + literal_cost + 1 + cost[after]
                choice[pos] = (literal_length, 0, None)
    result = bytearray()
    pos = 0
    while pos < size:
        selected = choice[pos]
        if selected is None:
            raise AssertionError(f"IAR encoder has no path at 0x{pos:x}")
        literals, run, distance = selected
        result += _emit(data[pos : pos + literals], run, distance)
        pos += literals + run
    decoded, consumed = decode(bytes(result), size)
    if decoded != data or consumed != len(result):
        raise AssertionError("IAR encoder round-trip failed")
    return bytes(result)
