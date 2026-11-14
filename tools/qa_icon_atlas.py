#!/usr/bin/env python3
"""Read-only QA inspection of a GUI bank entry and its keyboard-prompt sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MAX_SIDECAR_BYTES = 64 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_PIXELS = 16 * 1024 * 1024


def _u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _normalized_name(name: str) -> str:
    return name.replace("/", "\\").casefold()


@dataclass(frozen=True)
class SidecarEntry:
    bank_path: str
    offset: int
    size: int
    original: bytes
    keyboard: bytes


@dataclass(frozen=True)
class GuiBankEntry:
    name: str
    offset: int
    length: int


@dataclass(frozen=True)
class GuiBank:
    data: bytes
    entries: dict[str, GuiBankEntry]

    def __getitem__(self, name: str) -> GuiBankEntry:
        return self.entries[_normalized_name(name)]


def parse_sidecar(data: bytes) -> list[SidecarEntry]:
    """Parse the bounded KBPM v2 format emitted by keyboard_prompts.h."""
    if len(data) > MAX_SIDECAR_BYTES or len(data) < 12:
        raise ValueError("invalid sidecar size")
    if _u32le(data, 0) != 0x4D50424B:
        raise ValueError("invalid sidecar magic")
    if _u32le(data, 4) != 2:
        raise ValueError("unsupported sidecar version")
    count = _u32le(data, 8)
    if count > MAX_ENTRIES:
        raise ValueError("sidecar entry count exceeds limit")
    cursor = 12
    entries = []
    for _ in range(count):
        if cursor + 4 > len(data):
            raise ValueError("truncated sidecar path length")
        path_length = _u32le(data, cursor)
        cursor += 4
        if path_length == 0 or path_length > 4096 or cursor + path_length + 12 > len(data):
            raise ValueError("invalid or truncated sidecar path")
        try:
            bank_path = data[cursor : cursor + path_length].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid UTF-8 bank path") from exc
        cursor += path_length
        offset, size = struct.unpack_from("<QI", data, cursor)
        cursor += 12
        if size == 0 or size > MAX_ENTRY_BYTES or cursor + 2 * size > len(data):
            raise ValueError("invalid or truncated sidecar pixel payload")
        original = data[cursor : cursor + size]
        cursor += size
        keyboard = data[cursor : cursor + size]
        cursor += size
        entries.append(SidecarEntry(bank_path, offset, size, original, keyboard))
    if cursor != len(data):
        raise ValueError("unexpected trailing sidecar bytes")
    return entries


def parse_gui_bank(data: bytes) -> GuiBank:
    """Parse the GUI bank directory without modifying its payloads."""
    if len(data) < 19 or struct.unpack_from(">I", data, 4)[0] != 3 or data[8] != 0:
        raise ValueError("invalid GUI texture bank header")
    base_offset = struct.unpack_from(">I", data, 0)[0]
    packed_length = struct.unpack_from(">I", data, 9)[0]
    table_length = struct.unpack_from(">I", data, 13)[0]
    if (
        base_offset < 17
        or base_offset > len(data)
        or packed_length < 2
        or 17 + packed_length > base_offset
        or table_length < 4
        or table_length > 2 * 1024 * 1024
    ):
        raise ValueError("invalid GUI texture bank directory bounds")
    wrapper = int.from_bytes(data[17:19], "big")
    if wrapper >> 8 != 0x78 or wrapper % 31 != 0 or wrapper & 0x20:
        raise ValueError("invalid GUI bank DEFLATE wrapper")
    inflater = zlib.decompressobj(-15)
    try:
        table = inflater.decompress(data[19 : 17 + packed_length], table_length + 1)
        if len(table) <= table_length:
            table += inflater.flush(table_length + 1 - len(table))
    except zlib.error as exc:
        raise ValueError("invalid GUI bank directory DEFLATE stream") from exc
    # GuiTextureBank accepts both Z_STREAM_END and the SDK's observed Z_BUF_ERROR
    # case when input ends without a final block, provided the declared bytes
    # were produced exactly. A one-byte output allowance detects expansion past
    # the declared length; unconsumed_tail means the bound was hit.
    if len(table) != table_length or inflater.unconsumed_tail:
        raise ValueError("GUI bank directory length mismatch")
    count = struct.unpack_from(">I", table, 0)[0]
    if count > (len(table) - 4) // 14:
        raise ValueError("invalid GUI bank entry count")
    cursor = 4
    entries: dict[str, GuiBankEntry] = {}
    for _ in range(count):
        if cursor + 4 > len(table):
            raise ValueError("truncated GUI bank name length")
        name_length = struct.unpack_from(">I", table, cursor)[0]
        cursor += 4
        if name_length < 2 or cursor + name_length + 8 > len(table):
            raise ValueError("invalid GUI bank name bounds")
        name_bytes = table[cursor : cursor + name_length]
        if name_bytes[-1] != 0:
            raise ValueError("GUI bank name is not NUL-terminated")
        try:
            name = name_bytes[:-1].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid UTF-8 GUI bank name") from exc
        cursor += name_length
        relative_offset, length = struct.unpack_from(">II", table, cursor)
        cursor += 8
        if relative_offset > len(data) - base_offset or length > len(data) - base_offset - relative_offset:
            raise ValueError("GUI bank payload lies outside the bank")
        entries[_normalized_name(name)] = GuiBankEntry(name, base_offset + relative_offset, length)
    if cursor != len(table):
        raise ValueError("unexpected trailing GUI bank directory bytes")
    return GuiBank(data, entries)


def find_sidecar_entry(entries: list[SidecarEntry], bank_path: str, offset: int) -> SidecarEntry:
    matches = [
        entry
        for entry in entries
        if _normalized_name(entry.bank_path) == _normalized_name(bank_path)
        and entry.offset == offset
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one sidecar entry for {bank_path} at 0x{offset:X}, found {len(matches)}")
    return matches[0]


def source_matches_sidecar(bank_data: bytes, bank_entry: GuiBankEntry, sidecar_entry: SidecarEntry) -> bool:
    if bank_entry.offset != sidecar_entry.offset or bank_entry.length != sidecar_entry.size:
        return False
    start = bank_entry.offset
    end = start + bank_entry.length
    return end <= len(bank_data) and bank_data[start:end] == sidecar_entry.original


def _xenos_tiled_offset(x: int, y: int, pitch: int) -> int:
    # Mirrors src/gui/xenos_tiling.h (the Xenia-derived address function).
    macro = ((x >> 5) + (y >> 5) * (pitch >> 5)) << 9
    micro = ((x & 7) + ((y & 14) << 2)) << 2
    offset = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 1) << 4)
    bank = (((y & 8) >> 2) + (x >> 3)) & 3
    return (
        ((offset & ~511) << 3)
        + ((y & 16) << 7)
        + ((offset & 448) << 2)
        + (bank << 6)
        + (offset & 63)
    )


def tiled_a2_to_rgba(payload: bytes, width: int, height: int) -> bytes:
    """Convert A2 (ARGB byte order, Xenos tiled) pixels to linear PNG RGBA bytes."""
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ValueError("invalid or excessive texture dimensions")
    pixel_bytes = width * height * 4
    if len(payload) != pixel_bytes + 4 or int.from_bytes(payload[:4], "big") != pixel_bytes:
        raise ValueError("A2 payload size header does not match dimensions")
    out = bytearray(pixel_bytes)
    for y in range(height):
        for x in range(width):
            src_offset = 4 + _xenos_tiled_offset(x, y, width)
            dst_offset = (y * width + x) * 4
            if src_offset + 4 > len(payload):
                raise ValueError("Xenos tile offset exceeds texture payload")
            a, r, g, b = payload[src_offset : src_offset + 4]
            out[dst_offset : dst_offset + 4] = bytes((r, g, b, a))
    return bytes(out)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def encode_png_rgba(width: int, height: int, pixels: bytes) -> bytes:
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS or len(pixels) != width * height * 4:
        raise ValueError("invalid RGBA image dimensions or payload")
    rows = b"".join(b"\0" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(rows, 9)) + _png_chunk(b"IEND", b"")


def audit_atlas(game_root: Path, output_dir: Path, texture_name: str) -> dict:
    texture_bank_path = Path("data/art/gui/gui_textures.bnk")
    header_bank_path = Path("data/art/gui/gui_texture_headers.bnk")
    textures = (game_root / texture_bank_path).read_bytes()
    headers = (game_root / header_bank_path).read_bytes()
    sidecar_data = (game_root / "keyboard_prompts.bin").read_bytes()
    texture_bank = parse_gui_bank(textures)
    header_bank = parse_gui_bank(headers)
    texture_key = _normalized_name(texture_name)
    try:
        bank_entry = texture_bank.entries[texture_key]
        header_entry = header_bank.entries[texture_key]
    except KeyError as exc:
        raise ValueError(f"atlas entry missing from GUI banks: {texture_name}") from exc
    metadata = headers[header_entry.offset : header_entry.offset + header_entry.length]
    if len(metadata) < 24:
        raise ValueError("atlas header entry is too short")
    pixel_format = struct.unpack_from(">I", metadata, 12)[0]
    width, height = struct.unpack_from(">II", metadata, 16)
    if pixel_format != 0xA2:
        raise ValueError(f"atlas bank format is 0x{pixel_format:X}, expected uncompressed A2")
    sidecar_entry = find_sidecar_entry(
        parse_sidecar(sidecar_data), str(texture_bank_path), bank_entry.offset
    )
    source_payload = textures[bank_entry.offset : bank_entry.offset + bank_entry.length]
    matched = source_matches_sidecar(textures, bank_entry, sidecar_entry)
    images = {
        "source": source_payload,
        "sidecar-original": sidecar_entry.original,
        "sidecar-keyboard": sidecar_entry.keyboard,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {}
    for variant, payload in images.items():
        rgba = tiled_a2_to_rgba(payload, width, height)
        path = output_dir / f"{Path(texture_name).stem}-{variant}.png"
        with path.open("xb") as stream:
            stream.write(encode_png_rgba(width, height, rgba))
        output_paths[variant] = str(path)
    return {
        "texture": texture_name,
        "dimensions": [width, height],
        "format": f"0x{pixel_format:X}",
        "source_matches_sidecar_original": matched,
        "source_sha256": hashlib.sha256(source_payload).hexdigest(),
        "sidecar_original_sha256": hashlib.sha256(sidecar_entry.original).hexdigest(),
        "sidecar_keyboard_sha256": hashlib.sha256(sidecar_entry.keyboard).hexdigest(),
        "sidecar_pixel_differences": sum(a != b for a, b in zip(sidecar_entry.original, sidecar_entry.keyboard)),
        "images": output_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", required=True, type=Path, help="read-only QA game root")
    parser.add_argument("--out-dir", required=True, type=Path, help="new/empty evidence directory for PNGs")
    parser.add_argument(
        "--texture",
        default=r"art\gui\persistant\abyx.tex",
        help="texture-bank name to compare (default: shared A/B/X/Y atlas)",
    )
    args = parser.parse_args()
    try:
        result = audit_atlas(args.game_root, args.out_dir, args.texture)
    except (OSError, ValueError, struct.error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0 if result["source_matches_sidecar_original"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
