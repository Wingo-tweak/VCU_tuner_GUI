"""Data-driven layouts for confirmed Ninebot G3 VCU firmware versions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    version: str
    hashes: tuple[str, ...]
    decoded_length: int
    table_offset: int | None
    table_layout: str | None
    presets_offset: int | None
    drive_table_offset: int | None
    a2_offset: int | None
    a2_kind: str | None
    a4_offset: int | None
    writable: bool = True
    readonly_a0: int | None = None
    readonly_a1: int | None = None
    readonly_a2: int | None = None
    readonly_a3_1: int | None = None
    readonly_a3_2: int | None = None
    readonly_a4: int | None = None
    readonly_pair_location: str | None = None
    readonly_scalar_locations: tuple[str, str, str, str] | None = None


PROFILES = (
    Profile("1.4.8", ("d8b14d357177143bca4ef69072c0856fcdc63e40a282a8104b322d5dcaa0c299",), 0x2DDC, None, None, None, 0xE6A4, None, None, None, False,
            327, 20, 40, 15, 18, 16, "raw 0x98C6..0x9914 code constants; shared by modes for variant group 0/3/4",
            ("raw 0x9D24 ADD.W immediate", "raw 0x9D54 MOVS immediate", "raw 0x9D42 MOVS immediate", "raw 0x9906 MOVS immediate")),
    Profile("1.5.4", ("bc28bfadaeb6df391a77a08af7f2858cdc00123f408e93c617c011ce0233990f",), 0x2E40, None, None, None, 0xE714, None, None, None, False,
            491, 20, 0, 10, 14, 16, "raw 0x9A46..0x9A98 code constants; shared by all modes/variants",
            ("raw 0x9EA0 clear/store", "raw 0x9ECA MOVS immediate", "raw 0x9EB8 MOVS immediate", "raw 0x9A90 MOVS immediate")),
    Profile("1.5.5", ("b087b5afbd4257b75f66aff583cf46026d37ba3c8701266d470b9a2aa7676617",), 0x2F38, 0xBFC, "int_float", None, 0xDA64, 0x97BA, "clear", 0x93F8),
    Profile("1.5.6", ("bb74b5aef93054d4eb9252bcd01414ed0b8d0384ffe428d189c1bf8b49c59f18", "6b6a8c46dc7160760b730cddb303d15116b90f8be2cacf050477bddccd498297"), 0x2F38, 0xBFC, "float_float", None, 0xDAAC, 0x9812, "clear", 0x9448),
    Profile("1.5.8", ("ef740379e9d2a489a24f8517d48f9dd5ec06d7f2daa73e12fe37230fc990bbcd",), 0x2F90, 0xC08, "float_float", 0xD28, 0xEA60, 0xA818, "add", 0xA434),
    Profile("1.5.13", ("1f1e05eb79ab0bebdd0c016345f9cd9c25364bc1e7e46162414fba1f2093b108", "2a78a011827577045c108d017415d5149da64908901056d4b4a4337130da71d9", "8c9a65e4913e2d04687eeb20e493589780826946661e60c7f4d6e18f6dfb1144", "4ec89278bc288fb26df091b894a37ec7bb4f37fdc9eb38bb87bb85791c6278ca"), 0x2F74, 0xC08, "float_float", 0xD28, 0xD868, 0x967C, "add", 0x9300),
    Profile("1.5.15", ("534dc887dea2a02c58da4b39f412806c56ebe862b0263dfd012242470443a9c7",), 0x2FA0, 0xC18, "float_float", 0xD38, 0xE9EC, 0xA764, "add", 0xA384),
    Profile("1.6.1", ("7df86cc4a23f62ee8a96e2bf187954fd7268bf1723883a4591f8ca2e0f1ac782",), 0x2FA4, 0xC1C, "float_float", 0xD3C, 0xE614, 0xA2E6, "add", 0x9F0C),
    Profile("1.6.2", ("384a1d98ec36cc7071c6cbd389afa53a52ca1c4ebcdec6374902fc0eb6443693",), 0x2FA8, 0xC1C, "float_float", 0xD3C, 0xE604, 0xA2DA, "add", 0x9F00),
)

HASH_INDEX = {digest: profile for profile in PROFILES for digest in profile.hashes}
