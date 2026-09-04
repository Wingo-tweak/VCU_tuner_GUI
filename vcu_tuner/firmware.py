"""Validated firmware model and mutation/export backend."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import zipfile

from . import __version__, iar
from .profiles import HASH_INDEX, PROFILES, Profile

MODE_OFFSETS = {"Walk": 0x00, "Eco": 0x08, "Sport": 0x10, "Drive": 0x20}
PRESET_OFFSETS = {"Sport / reg6E=1": 0x00, "Sport / reg6E=2": 0x08, "Sport / reg6E=3": 0x10}
VARIANT_STRIDE = 0x30
DRIVE_VARIANT_STRIDE = 0x24
DRIVE_OFFSET = 0x0C
SPORT_FALLBACK_OFFSET = 0x18
BUNDLED_TEMPLATE_MANIFEST = Path(__file__).resolve().parents[1] / "assets" / "ota_templates" / "manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


@dataclass(frozen=True)
class PairValue:
    key: str
    label: str
    decoded_offset: int | None
    a0: int
    a1: int
    editable: bool = True
    location: str = ""


@dataclass(frozen=True)
class ScalarValue:
    key: str
    label: str
    value: int
    editable: bool
    scope: str
    location: str


class FirmwareError(ValueError):
    pass


def bundled_template_details() -> dict:
    try:
        details = json.loads(BUNDLED_TEMPLATE_MANIFEST.read_text(encoding="utf-8"))
        path = BUNDLED_TEMPLATE_MANIFEST.parent / details["default"]
        if not path.is_file():
            raise FirmwareError("bundled OTA template file is missing")
        if sha256(path.read_bytes()) != details["sha256"]:
            raise FirmwareError("bundled OTA template SHA-256 mismatch")
        return {**details, "path": path}
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise FirmwareError(f"invalid bundled OTA template manifest: {exc}") from exc


def _read_ota_entries(path: str | Path) -> list[tuple[zipfile.ZipInfo, bytes]]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    except (OSError, zipfile.BadZipFile) as exc:
        raise FirmwareError(f"cannot read OTA template: {exc}") from exc
    names = {item.filename for item, _ in entries}
    if not {"FIRM.bin", "info.json"}.issubset(names):
        raise FirmwareError("OTA template must contain FIRM.bin and info.json")
    try:
        info_data = next(data for item, data in entries if item.filename == "info.json")
        info = json.loads(info_data.decode("utf-8"))
        firmware = info["firmware"]
        if not isinstance(firmware, dict) or not isinstance(firmware.get("md5"), str):
            raise KeyError("firmware.md5")
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        raise FirmwareError(f"unsupported OTA info.json schema: {exc}") from exc
    return entries


def validate_ota_template(path: str | Path) -> None:
    _read_ota_entries(path)


def _ror32(value: int, rotation: int) -> int:
    rotation &= 31
    return ((value >> rotation) | (value << (32 - rotation))) & 0xFFFFFFFF if rotation else value


def thumb_expand_imm(imm12: int) -> int | None:
    imm8 = imm12 & 0xFF
    if (imm12 >> 10) == 0:
        mode = (imm12 >> 8) & 3
        if mode == 0:
            return imm8
        if imm8 == 0:
            return None
        if mode == 1:
            return (imm8 << 16) | imm8
        if mode == 2:
            return (imm8 << 24) | (imm8 << 8)
        return imm8 * 0x01010101
    return _ror32(0x80 | (imm12 & 0x7F), (imm12 >> 7) & 0x1F)


def encode_thumb_imm(value: int) -> int | None:
    for imm12 in range(0x1000):
        if thumb_expand_imm(imm12) == value:
            return imm12
    return None


def decode_add_r0_immediate(blob: bytes, offset: int) -> int:
    h1, h2 = struct.unpack_from("<HH", blob, offset)
    if h1 & ~(1 << 10) != 0xF100 or h2 & ~0x70FF:
        raise FirmwareError(f"ADD.W r0,r0,#imm opcode is not verified at raw 0x{offset:X}")
    imm12 = (((h1 >> 10) & 1) << 11) | (((h2 >> 12) & 7) << 8) | (h2 & 0xFF)
    value = thumb_expand_imm(imm12)
    if value is None:
        raise FirmwareError("invalid Thumb modified immediate")
    return value


def patch_add_r0_immediate(blob: bytearray, offset: int, value: int) -> None:
    imm12 = encode_thumb_imm(value)
    if imm12 is None:
        raise FirmwareError(f"{value} cannot be encoded by the existing Thumb ADD.W without expanding code")
    h1, h2 = struct.unpack_from("<HH", blob, offset)
    decode_add_r0_immediate(blob, offset)
    h1 = (h1 & ~(1 << 10)) | (((imm12 >> 11) & 1) << 10)
    h2 = (h2 & ~0x70FF) | (((imm12 >> 8) & 7) << 12) | (imm12 & 0xFF)
    struct.pack_into("<HH", blob, offset, h1, h2)


def _read_movs(blob: bytes, offset: int, register: int) -> int:
    immediate, opcode = blob[offset : offset + 2]
    if opcode != 0x20 + register:
        raise FirmwareError(f"MOVS r{register},#imm is not verified at raw 0x{offset:X}")
    return immediate


def _write_movs(blob: bytearray, offset: int, register: int, value: int) -> None:
    _read_movs(blob, offset, register)
    blob[offset] = value


def _read_pair(unpacked: bytes, profile: Profile, offset: int) -> tuple[int, int]:
    if profile.table_layout == "int_float":
        a1_units = struct.unpack_from("<i", unpacked, offset)[0]
        a1 = a1_units * 10
    else:
        a1_float = struct.unpack_from("<f", unpacked, offset)[0]
        if not math.isfinite(a1_float):
            raise FirmwareError("A1 contains a non-finite float")
        a1 = int(f32(a1_float * 10.0))
    a0_float = struct.unpack_from("<f", unpacked, offset + 4)[0]
    if not math.isfinite(a0_float):
        raise FirmwareError("A0 contains a non-finite float")
    return int(f32(a0_float * 32768.0)), a1


def _write_pair(unpacked: bytearray, profile: Profile, offset: int, a0: int, a1: int) -> None:
    if not 0 <= a0 <= 0xFFFF or not 0 <= a1 <= 0xFF:
        raise FirmwareError("A0 must be 0..65535 and A1 must be 0..255")
    a0_float = f32(a0 / 32768.0)
    if int(f32(a0_float * 32768.0)) != a0:
        raise FirmwareError(f"A0={a0} does not round-trip exactly through float32")
    if profile.table_layout == "int_float":
        if a1 % 10:
            raise FirmwareError("VCU 1.5.5 stores A1 as an integer: effective A1 must be divisible by 10")
        struct.pack_into("<i", unpacked, offset, a1 // 10)
    else:
        a1_float = f32(a1 / 10.0)
        if int(f32(a1_float * 10.0)) != a1:
            raise FirmwareError(f"A1={a1} does not round-trip exactly through float32")
        struct.pack_into("<f", unpacked, offset, a1_float)
    struct.pack_into("<f", unpacked, offset + 4, a0_float)


def _a3_offsets(profile: Profile) -> tuple[int, int]:
    assert profile.a2_offset is not None
    return ((profile.a2_offset + 0x28, profile.a2_offset + 0x1A)
            if profile.a2_kind == "clear"
            else (profile.a2_offset + 0x2C, profile.a2_offset + 0x1E))


def _validate_profile(blob: bytes, unpacked: bytes, descriptor: iar.Descriptor, profile: Profile) -> list[str]:
    errors: list[str] = []
    if descriptor.output_length != profile.decoded_length:
        return ["decoded RAM length does not match"]
    if not profile.writable:
        return errors
    try:
        assert profile.table_offset is not None and profile.drive_table_offset is not None
        if profile.table_offset + 6 * VARIANT_STRIDE > len(unpacked):
            raise FirmwareError("A0/A1 table exceeds decoded RAM")
        for relative in MODE_OFFSETS.values():
            a0, a1 = _read_pair(unpacked, profile, profile.table_offset + relative)
            if not (-1 <= a0 <= 0x20000 and -1000 <= a1 <= 2000):
                raise FirmwareError("implausible variant 0 A0/A1 values")
        if profile.presets_offset is not None:
            for relative in PRESET_OFFSETS.values():
                _read_pair(unpacked, profile, profile.presets_offset + relative)
        limit_end = profile.drive_table_offset + 6 * DRIVE_VARIANT_STRIDE
        if limit_end > len(blob):
            raise FirmwareError("speed-limit table exceeds the raw image")
        pointer = struct.pack("<I", iar.IMAGE_RUNTIME_BASE + profile.drive_table_offset)
        if blob.count(pointer) == 0:
            raise FirmwareError("no confirming pointer to the speed-limit table")
        assert profile.a2_offset is not None and profile.a4_offset is not None
        if blob[profile.a2_offset : profile.a2_offset + 2] != b"\xC0\xB2":
            raise FirmwareError("UXTB anchor before the A2 producer is missing")
        if profile.a2_kind == "add":
            immediate = decode_add_r0_immediate(blob, profile.a2_offset + 2)
            if immediate & 0xFF:
                raise FirmwareError("A2 ADD immediate is not divisible by 0x100")
        elif blob[profile.a2_offset + 2 : profile.a2_offset + 4] != b"\x60\x81":
            raise FirmwareError("A2 clear producer does not match")
        a3_1, a3_2 = _a3_offsets(profile)
        _read_movs(blob, a3_1, 0)
        _read_movs(blob, a3_2, 0)
        _read_movs(blob, profile.a4_offset, 1)
    except (AssertionError, IndexError, struct.error, FirmwareError) as exc:
        errors.append(str(exc))
    return errors


class FirmwareDocument:
    def __init__(self, path: Path, raw: bytes, ota_entries: list[tuple[zipfile.ZipInfo, bytes]] | None = None):
        self.path = path
        self.raw = raw
        self.ota_entries = ota_entries
        self.digest = sha256(raw)
        try:
            self.descriptor = iar.find_initialized_data_descriptor(raw)
            self.unpacked, self.stream_consumed = iar.decode(raw[self.descriptor.source_offset :], self.descriptor.output_length)
        except ValueError as exc:
            raise FirmwareError(str(exc)) from exc
        exact = HASH_INDEX.get(self.digest)
        if exact:
            errors = _validate_profile(raw, self.unpacked, self.descriptor, exact)
            if errors:
                raise FirmwareError("known SHA-256, but structural checks failed: " + "; ".join(errors))
            self.profile = exact
            self.trust = "exact"
        else:
            matches = []
            for candidate in PROFILES:
                if candidate.writable and not _validate_profile(raw, self.unpacked, self.descriptor, candidate):
                    matches.append(candidate)
            if len(matches) != 1:
                detail = "was not found" if not matches else "is ambiguous: " + ", ".join(p.version for p in matches)
                raise FirmwareError(f"unknown SHA-256; structural profile {detail}. Writing is disabled")
            self.profile = matches[0]
            self.trust = "structural"

    @property
    def read_only(self) -> bool:
        return not self.profile.writable

    @classmethod
    def open(cls, path: str | Path) -> "FirmwareDocument":
        source = Path(path)
        if source.suffix.lower() == ".zip":
            entries = _read_ota_entries(source)
            raw = next(data for item, data in entries if item.filename == "FIRM.bin")
            return cls(source, raw, entries)
        return cls(source, source.read_bytes())

    @property
    def container(self) -> str:
        return "OTA ZIP" if self.ota_entries else "raw binary"

    def pairs(self) -> list[PairValue]:
        profile = self.profile
        if not profile.writable:
            assert profile.readonly_a0 is not None and profile.readonly_a1 is not None
            return [
                PairValue("mode_" + name.lower(), name, None, profile.readonly_a0, profile.readonly_a1, False, profile.readonly_pair_location or "code constants")
                for name in MODE_OFFSETS
            ]
        assert profile.table_offset is not None
        result: list[PairValue] = []
        for name, relative in MODE_OFFSETS.items():
            offset = profile.table_offset + relative
            a0, a1 = _read_pair(self.unpacked, profile, offset)
            editable = not (name == "Sport" and profile.presets_offset is not None)
            label = name if editable else "Sport working slot (overwritten by reg6E profile)"
            result.append(PairValue("mode_" + name.lower(), label, offset, a0, a1, editable, f"decoded RAM +0x{offset:X}"))
        if profile.presets_offset is not None:
            for name, relative in PRESET_OFFSETS.items():
                offset = profile.presets_offset + relative
                a0, a1 = _read_pair(self.unpacked, profile, offset)
                result.append(PairValue("preset_" + name[-1], name, offset, a0, a1, True, f"decoded RAM +0x{offset:X}"))
        return result

    def scalars(self) -> list[ScalarValue]:
        p = self.profile
        if not p.writable:
            assert p.drive_table_offset is not None and p.readonly_scalar_locations is not None
            values = (p.readonly_a2, p.readonly_a3_1, p.readonly_a3_2, p.readonly_a4)
            if any(value is None for value in values):
                raise FirmwareError("incomplete read-only profile constants")
            locations = p.readonly_scalar_locations
            return [
                ScalarValue("a2", "A2 default", int(values[0]), False, "code constant", locations[0]),
                ScalarValue("a3_1", "A3 default, selector 1", int(values[1]), False, "code constant", locations[1]),
                ScalarValue("a3_2", "A3 default, selector 2", int(values[2]), False, "code constant", locations[2]),
                ScalarValue("a4", "A4 default", int(values[3]), False, "variant 0/3/4 code path", locations[3]),
                ScalarValue("drive", "Drive speed guard/fallback", struct.unpack_from("<I", self.raw, p.drive_table_offset + DRIVE_OFFSET)[0], False, "vehicle variant 0", f"raw 0x{p.drive_table_offset + DRIVE_OFFSET:X}, uint32"),
            ]
        assert p.a2_offset is not None and p.a4_offset is not None and p.drive_table_offset is not None
        if p.a2_kind == "add":
            a2 = decode_add_r0_immediate(self.raw, p.a2_offset + 2) >> 8
            a2_edit = True
            a2_loc = f"raw 0x{p.a2_offset + 2:X}, Thumb ADD.W immediate"
        else:
            a2, a2_edit = 0, False
            a2_loc = f"raw 0x{p.a2_offset:X}, producer clears A2"
        a3_1_offset, a3_2_offset = _a3_offsets(p)
        drive_offset = p.drive_table_offset + DRIVE_OFFSET
        return [
            ScalarValue("a2", "A2 default", a2, a2_edit, "global for all variants", a2_loc),
            ScalarValue("a3_1", "A3 default, selector 1", _read_movs(self.raw, a3_1_offset, 0), True, "conditional producer branch; override may replace it", f"raw 0x{a3_1_offset:X}"),
            ScalarValue("a3_2", "A3 default, selector 2", _read_movs(self.raw, a3_2_offset, 0), True, "conditional producer branch; override may replace it", f"raw 0x{a3_2_offset:X}"),
            ScalarValue("a4", "A4 default", _read_movs(self.raw, p.a4_offset, 1), True, "variant group 0/3/4", f"raw 0x{p.a4_offset:X}"),
            ScalarValue("drive", "Drive speed guard/fallback", struct.unpack_from("<I", self.raw, drive_offset)[0], True, "vehicle variant 0 only", f"raw 0x{drive_offset:X}, uint32"),
            ScalarValue("sport_fallback", "Sport speed fallback/default", struct.unpack_from("<I", self.raw, p.drive_table_offset + SPORT_FALLBACK_OFFSET)[0], True, "variant 0; used only when reg48 high byte < 5", f"raw 0x{p.drive_table_offset + SPORT_FALLBACK_OFFSET:X}, uint32"),
        ]

    def build(self, pair_changes: dict[str, tuple[int, int]], scalar_changes: dict[str, int]) -> tuple[bytes, dict]:
        p = self.profile
        if not p.writable:
            raise FirmwareError(f"VCU {p.version} is a read-only profile; export is disabled")
        raw = bytearray(self.raw)
        unpacked = bytearray(self.unpacked)
        original_pairs = {item.key: item for item in self.pairs()}
        original_scalars = {item.key: item for item in self.scalars()}
        changes: list[dict] = []
        pair_dirty = False
        for key, (a0, a1) in pair_changes.items():
            if key not in original_pairs or not original_pairs[key].editable:
                raise FirmwareError(f"field {key} is not writable")
            item = original_pairs[key]
            assert item.decoded_offset is not None
            if (a0, a1) != (item.a0, item.a1):
                _write_pair(unpacked, p, item.decoded_offset, a0, a1)
                pair_dirty = True
                changes.append({"field": key, "storage": f"decoded RAM +0x{item.decoded_offset:X}", "old": {"A0": item.a0, "A1": item.a1}, "new": {"A0": a0, "A1": a1}})
        for key, value in scalar_changes.items():
            if key not in original_scalars or not original_scalars[key].editable:
                raise FirmwareError(f"field {key} is not writable")
            if not 0 <= value <= 0xFF:
                raise FirmwareError(f"{key}: value must be 0..255")
            item = original_scalars[key]
            if value != item.value:
                if key == "a2":
                    assert p.a2_offset is not None
                    patch_add_r0_immediate(raw, p.a2_offset + 2, value << 8)
                elif key in ("a3_1", "a3_2"):
                    offsets = _a3_offsets(p)
                    _write_movs(raw, offsets[0 if key == "a3_1" else 1], 0, value)
                elif key == "a4":
                    assert p.a4_offset is not None
                    _write_movs(raw, p.a4_offset, 1, value)
                elif key == "drive":
                    assert p.drive_table_offset is not None
                    struct.pack_into("<I", raw, p.drive_table_offset + DRIVE_OFFSET, value)
                elif key == "sport_fallback":
                    assert p.drive_table_offset is not None
                    struct.pack_into("<I", raw, p.drive_table_offset + SPORT_FALLBACK_OFFSET, value)
                changes.append({"field": key, "storage": item.location, "scope": item.scope, "old": item.value, "new": value})
        next_desc = iar.read_descriptor(self.raw, self.descriptor.offset + 16)
        strict_capacity = next_desc.source_offset - self.descriptor.source_offset
        if pair_dirty:
            packed = iar.encode(bytes(unpacked))
            overlap = max(0, len(packed) - strict_capacity)
            if overlap:
                function_offset = next_desc.function_runtime - iar.IMAGE_RUNTIME_BASE
                signature = self.raw[function_offset : function_offset + len(iar.ZERO_FILL_SIGNATURE)]
                if next_desc.destination != iar.RAM_BASE + p.decoded_length or signature != iar.ZERO_FILL_SIGNATURE:
                    raise FirmwareError(
                        "repacked IAR stream overlaps the next source without a verified zero-fill consumer. "
                        "Try slightly changing one or more A0/A1 values and export again; different float bit patterns compress differently"
                    )
            if self.descriptor.source_offset + len(packed) > len(raw):
                raise FirmwareError(
                    "repacked IAR stream does not fit in the raw image. "
                    "Try slightly changing one or more A0/A1 values and export again; different float bit patterns compress differently"
                )
            raw[self.descriptor.source_offset : self.descriptor.source_offset + len(packed)] = packed
        else:
            packed = self.raw[self.descriptor.source_offset : self.descriptor.source_offset + self.stream_consumed]
            overlap = max(0, self.stream_consumed - strict_capacity)
        result = bytes(raw)
        check = FirmwareDocument._readback(result, p)
        expected_pairs = {**{k: (v.a0, v.a1) for k, v in original_pairs.items()}, **pair_changes}
        if {x.key: (x.a0, x.a1) for x in check.pairs()} != expected_pairs:
            raise AssertionError("final A0/A1 readback differs from the requested values")
        expected_scalars = {**{k: v.value for k, v in original_scalars.items()}, **scalar_changes}
        if {x.key: x.value for x in check.scalars()} != expected_scalars:
            raise AssertionError("final scalar readback differs from the requested values")
        raw_diff = [offset for offset, (before, after) in enumerate(zip(self.raw, result)) if before != after]
        audit = {
            "tool": f"Ninebot G3 VCU tuner {__version__}",
            "profile": p.version,
            "recognition": self.trust,
            "source": str(self.path.resolve()),
            "source_sha256": self.digest,
            "output_sha256": sha256(result),
            "output_md5": md5(result),
            "firmware_length": len(result),
            "variant": 0,
            "changes": changes,
            "raw_diff": {"count": len(raw_diff), "minimum": f"0x{min(raw_diff):X}" if raw_diff else None, "maximum": f"0x{max(raw_diff):X}" if raw_diff else None},
            "iar": {"descriptor_raw_offset": f"0x{self.descriptor.offset:X}", "decoded_length": p.decoded_length, "stream_raw_start": f"0x{self.descriptor.source_offset:X}", "original_consumed": self.stream_consumed, "new_consumed": len(packed), "strict_capacity": strict_capacity, "zero_fill_source_overlap": overlap},
        }
        return result, audit

    @classmethod
    def _readback(cls, raw: bytes, profile: Profile) -> "FirmwareDocument":
        obj = cls.__new__(cls)
        obj.path = Path("<readback>")
        obj.raw = raw
        obj.ota_entries = None
        obj.digest = sha256(raw)
        obj.descriptor = iar.find_initialized_data_descriptor(raw)
        obj.unpacked, obj.stream_consumed = iar.decode(raw[obj.descriptor.source_offset :], obj.descriptor.output_length)
        errors = _validate_profile(raw, obj.unpacked, obj.descriptor, profile)
        if errors:
            raise FirmwareError("readback structure failed: " + "; ".join(errors))
        obj.profile, obj.trust = profile, "readback"
        return obj

    def export_raw(self, output: str | Path, pair_changes: dict[str, tuple[int, int]], scalar_changes: dict[str, int]) -> tuple[Path, Path]:
        destination = Path(output)
        audit_path = destination.with_suffix(destination.suffix + ".audit.json")
        if destination.resolve() == self.path.resolve() or destination.exists() or audit_path.exists():
            raise FirmwareError("the source file or an existing output file will not be overwritten")
        result, audit = self.build(pair_changes, scalar_changes)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(result)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination, audit_path

    def export_ota(self, output: str | Path, pair_changes: dict[str, tuple[int, int]], scalar_changes: dict[str, int], template: str | Path | None = None) -> tuple[Path, Path]:
        destination = Path(output)
        audit_path = destination.with_suffix(destination.suffix + ".audit.json")
        if destination.resolve() == self.path.resolve() or destination.exists() or audit_path.exists():
            raise FirmwareError("the source file or an existing output file will not be overwritten")
        if template is not None:
            template_path = Path(template)
            entries = _read_ota_entries(template_path)
            template_source = str(template_path.resolve())
        elif self.ota_entries is not None:
            entries = self.ota_entries
            template_source = str(self.path.resolve())
        else:
            details = bundled_template_details()
            template_path = details["path"]
            entries = _read_ota_entries(template_path)
            template_source = f"bundled: {details['display_name']} ({details['sha256']})"
        result, audit = self.build(pair_changes, scalar_changes)
        info_data = next(data for item, data in entries if item.filename == "info.json")
        info = json.loads(info_data.decode("utf-8"))
        firmware_info = info["firmware"]
        output_name = f"VCU {self.profile.version} (G3 calibration tuner output)"
        output_description = f"Generated from VCU {self.profile.version} by Ninebot G3 VCU calibration tuner"
        firmware_info["md5"] = md5(result)
        firmware_info["displayName"] = output_name
        for container in (info, firmware_info):
            for key in ("description", "Description"):
                if key in container:
                    container[key] = output_description
        encoded_info = (json.dumps(info, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w") as output_zip:
            for item, data in entries:
                if item.filename == "FIRM.bin":
                    data = result
                elif item.filename == "info.json":
                    data = encoded_info
                output_zip.writestr(item, data)
        with zipfile.ZipFile(destination, "r") as check:
            if check.read("FIRM.bin") != result:
                raise AssertionError("OTA ZIP readback failed")
            check_info = json.loads(check.read("info.json"))
            if check_info["firmware"]["md5"].lower() != md5(result):
                raise AssertionError("OTA metadata MD5 readback failed")
        audit["ota"] = {
            "template": template_source,
            "metadata_display_name": output_name,
            "output_zip_sha256": sha256(destination.read_bytes()),
        }
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination, audit_path
