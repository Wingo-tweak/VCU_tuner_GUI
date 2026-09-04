"""Rebuild the bundled OTA template from the exact stock VCU 1.5.13 image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT / "assets" / "ota_templates"
DEFAULT_OUTPUT = ASSET_DIR / "VCU_readback_1.5.13.zip"
MANIFEST = ASSET_DIR / "manifest.json"

STOCK_SHA256 = "1f1e05eb79ab0bebdd0c016345f9cd9c25364bc1e7e46162414fba1f2093b108"
READBACK_SHA256 = "2a78a011827577045c108d017415d5149da64908901056d4b4a4337130da71d9"
IMAGE_LENGTH = 56820
PATCH_OFFSET = 0x7AB4
ORIGINAL_BASE = 0x2000641A
READBACK_BASE = 0x20003900
DISPLAY_NAME = "Stock-based VCU 1.5.13 (Compat) A-parameter readback template"


def digest(data: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, data).hexdigest()


def zip_item(name: str) -> zipfile.ZipInfo:
    item = zipfile.ZipInfo(name, (2026, 9, 3, 0, 0, 0))
    item.compress_type = zipfile.ZIP_STORED
    item.create_system = 0
    item.external_attr = 0x20
    return item


def build(stock_path: Path, output: Path) -> dict:
    stock = stock_path.read_bytes()
    if len(stock) != IMAGE_LENGTH:
        raise ValueError(f"stock image must be {IMAGE_LENGTH} bytes, got {len(stock)}")
    if digest(stock) != STOCK_SHA256:
        raise ValueError("source is not the exact stock VCU 1.5.13 (Compat) image")
    if struct.unpack_from("<I", stock, PATCH_OFFSET)[0] != ORIGINAL_BASE:
        raise ValueError(f"readback source literal mismatch at raw 0x{PATCH_OFFSET:X}")

    firmware = bytearray(stock)
    struct.pack_into("<I", firmware, PATCH_OFFSET, READBACK_BASE)
    firmware = bytes(firmware)
    changed = [index for index, (left, right) in enumerate(zip(stock, firmware)) if left != right]
    if changed != [PATCH_OFFSET, PATCH_OFFSET + 1]:
        raise AssertionError(f"unexpected firmware diff: {changed}")
    if digest(firmware) != READBACK_SHA256:
        raise AssertionError("clean readback firmware SHA-256 mismatch")

    info = {
        "schemaVersion": 2,
        "firmware": {
            "displayName": "1.5.13 (Compat) + A-parameter readback",
            "models": ["g3"],
            "type": "vcu",
            "compatible": ["g3_VCU_AT32"],
            "md5": digest(firmware, "md5"),
        },
    }
    encoded_info = (json.dumps(info, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(zip_item("FIRM.bin"), firmware)
        archive.writestr(zip_item("info.json"), encoded_info)

    archive_hash = digest(output.read_bytes())
    manifest = {
        "default": output.name,
        "display_name": DISPLAY_NAME,
        "provenance": (
            f"Exact stock VCU 1.5.13 (Compat) {STOCK_SHA256}; only raw 0x{PATCH_OFFSET:X} "
            f"literal 0x{ORIGINAL_BASE:08X} -> 0x{READBACK_BASE:08X}"
        ),
        "sha256": archive_hash,
        "schema_version": 2,
        "firmware_type": "vcu",
        "compatible": ["g3_VCU_AT32"],
        "stock_firmware_sha256": STOCK_SHA256,
        "readback_firmware_sha256": READBACK_SHA256,
        "firmware_diff_offsets": [f"0x{PATCH_OFFSET:X}", f"0x{PATCH_OFFSET + 1:X}"],
    }
    if output.resolve() == DEFAULT_OUTPUT.resolve():
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path, help="exact stock VCU 1.5.13 (Compat) raw image")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build(args.stock, args.output)
    print(f"Created {args.output}")
    print(f"OTA SHA-256: {manifest['sha256']}")
    print(f"FIRM SHA-256: {manifest['readback_firmware_sha256']}")


if __name__ == "__main__":
    main()
