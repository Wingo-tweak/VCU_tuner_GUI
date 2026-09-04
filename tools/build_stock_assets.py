"""Validate and copy the supported exact-stock VCU images into assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


PROJECT = Path(__file__).resolve().parents[1]
DESTINATION = PROJECT / "assets" / "VCU_Stock_Firmware"

STOCK = {
    "1.4.8": ("VCU_1.4.8_compat.bin", "d8b14d357177143bca4ef69072c0856fcdc63e40a282a8104b322d5dcaa0c299"),
    "1.5.4": ("VCU_1.5.4_compat.bin", "bc28bfadaeb6df391a77a08af7f2858cdc00123f408e93c617c011ce0233990f"),
    "1.5.5": ("VCU_1.5.5_compat.bin", "b087b5afbd4257b75f66aff583cf46026d37ba3c8701266d470b9a2aa7676617"),
    "1.5.6": ("VCU_1.5.6_compat.bin", "bb74b5aef93054d4eb9252bcd01414ed0b8d0384ffe428d189c1bf8b49c59f18"),
    "1.5.8": ("VCU_1.5.8_compat.bin", "ef740379e9d2a489a24f8517d48f9dd5ec06d7f2daa73e12fe37230fc990bbcd"),
    "1.5.13": ("VCU_1.5.13_compat.bin", "1f1e05eb79ab0bebdd0c016345f9cd9c25364bc1e7e46162414fba1f2093b108"),
    "1.5.15": ("VCU_1.5.15_compat.bin", "534dc887dea2a02c58da4b39f412806c56ebe862b0263dfd012242470443a9c7"),
    "1.6.1": ("VCU_1.6.1_compat.bin", "7df86cc4a23f62ee8a96e2bf187954fd7268bf1723883a4591f8ca2e0f1ac782"),
    "1.6.2": ("VCU_1.6.2_compat.bin", "384a1d98ec36cc7071c6cbd389afa53a52ca1c4ebcdec6374902fc0eb6443693"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(source_directory: Path) -> dict:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    entries = []
    for version, (filename, expected_hash) in STOCK.items():
        source = source_directory / filename
        data = source.read_bytes()
        actual_hash = sha256(data)
        if actual_hash != expected_hash:
            raise ValueError(f"{filename}: expected {expected_hash}, got {actual_hash}")
        destination = DESTINATION / filename
        shutil.copyfile(source, destination)
        entries.append({
            "version": version,
            "display_name": f"VCU {version} (Compat) stock",
            "file": filename,
            "bytes": len(data),
            "sha256": actual_hash,
            "firmware_type": "vcu",
            "compatible": ["g3_VCU_AT32"],
            "flags": ["stock", "compat"],
        })
    manifest = {"schema_version": 1, "entries": entries}
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path, help="directory containing the exact named stock binaries")
    args = parser.parse_args()
    manifest = build(args.source_directory)
    print(f"Copied {len(manifest['entries'])} verified stock VCU images to {DESTINATION}")


if __name__ == "__main__":
    main()
