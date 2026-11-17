import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "qa_icon_atlas", ROOT / "tools" / "qa_icon_atlas.py"
)
qa_icon_atlas = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = qa_icon_atlas
SPEC.loader.exec_module(qa_icon_atlas)

audit_atlas = qa_icon_atlas.audit_atlas
find_sidecar_entry = qa_icon_atlas.find_sidecar_entry
parse_gui_bank = qa_icon_atlas.parse_gui_bank
parse_sidecar = qa_icon_atlas.parse_sidecar
source_matches_sidecar = qa_icon_atlas.source_matches_sidecar
tiled_a2_to_rgba = qa_icon_atlas.tiled_a2_to_rgba


def make_gui_bank(entries, clean_deflate_end=True):
    directory = bytearray(struct.pack(">I", len(entries)))
    payloads = bytearray()
    for name, payload in entries:
        encoded = name.encode("utf-8") + b"\0"
        directory.extend(struct.pack(">I", len(encoded)))
        directory.extend(encoded)
        directory.extend(struct.pack(">II", len(payloads), len(payload)))
        payloads.extend(payload)
    compressor = zlib.compressobj(level=9, wbits=-15)
    flush_mode = zlib.Z_FINISH if clean_deflate_end else zlib.Z_SYNC_FLUSH
    raw_deflate = compressor.compress(directory) + compressor.flush(flush_mode)
    packed_length = len(raw_deflate) + 2
    base_offset = 17 + packed_length
    header = struct.pack(">IIBII", base_offset, 3, 0, packed_length, len(directory))
    return header + b"\x78\x9c" + raw_deflate + payloads


def make_sidecar(entries):
    out = bytearray(struct.pack("<III", 0x4D50424B, 2, len(entries)))
    for bank_path, offset, original, keyboard in entries:
        encoded = bank_path.encode("utf-8")
        if len(original) != len(keyboard):
            raise ValueError("synthetic entry payloads must have equal sizes")
        out.extend(struct.pack("<I", len(encoded)))
        out.extend(encoded)
        out.extend(struct.pack("<QI", offset, len(original)))
        out.extend(original)
        out.extend(keyboard)
    return bytes(out)


def tiled_fixture(width, height, pixels):
    payload = bytearray(4 + width * height * 4)
    struct.pack_into(">I", payload, 0, width * height * 4)
    # These fixed offsets are the Xenos 64x64 tile positions exercised below.
    offsets = {(0, 0): 0, (32, 0): 4096, (0, 32): 8192, (63, 63): 16252}
    for xy, argb in pixels.items():
        offset = offsets[xy]
        payload[4 + offset : 4 + offset + 4] = bytes(argb)
    return bytes(payload)


class QaIconAtlasTests(unittest.TestCase):
    def test_synthetic_atlas_audit_writes_evidence_without_overwriting_it(self):
        texture_name = r"Art\GUI\Persistant\abyx.tex"
        texture_payload = tiled_fixture(64, 64, {(0, 0): (255, 1, 2, 3)})
        metadata = bytearray(24)
        struct.pack_into(">I", metadata, 12, 0xA2)
        struct.pack_into(">II", metadata, 16, 64, 64)
        texture_bank = make_gui_bank([(texture_name, texture_payload)])
        bank_entry = parse_gui_bank(texture_bank)[texture_name.lower()]
        header_bank = make_gui_bank([(texture_name, bytes(metadata))])
        sidecar = make_sidecar(
            [("data/art/gui/gui_textures.bnk", bank_entry.offset, texture_payload, texture_payload)]
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_root = root / "game"
            gui = game_root / "data" / "art" / "gui"
            gui.mkdir(parents=True)
            (gui / "gui_textures.bnk").write_bytes(texture_bank)
            (gui / "gui_texture_headers.bnk").write_bytes(header_bank)
            (game_root / "keyboard_prompts.bin").write_bytes(sidecar)
            evidence = root / "evidence"

            result = audit_atlas(game_root, evidence, texture_name)

            self.assertEqual(result["dimensions"], [64, 64])
            self.assertTrue(result["source_matches_sidecar_original"])
            outputs = [Path(path) for path in result["images"].values()]
            self.assertEqual(len(outputs), 3)
            self.assertTrue(all(path.is_file() for path in outputs))
            self.assertTrue(
                all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in outputs)
            )
            originals = [path.read_bytes() for path in outputs]

            with self.assertRaises(FileExistsError):
                audit_atlas(game_root, evidence, texture_name)

            self.assertEqual([path.read_bytes() for path in outputs], originals)

    def test_sidecar_selects_original_and_keyboard_variants_by_bank_offset(self):
        original = b"orig"
        keyboard = b"keys"
        sidecar = parse_sidecar(
            make_sidecar([("data/art/gui/gui_textures.bnk", 17, original, keyboard)])
        )

        entry = find_sidecar_entry(
            sidecar, "data/art/gui/gui_textures.bnk", 17
        )

        self.assertEqual(entry.original, original)
        self.assertEqual(entry.keyboard, keyboard)

    def test_sidecar_rejects_truncated_variant_data(self):
        data = make_sidecar([("gui_textures.bnk", 0, b"abcd", b"wxyz")])[:-1]

        with self.assertRaises(ValueError):
            parse_sidecar(data)

    def test_gui_bank_parser_resolves_case_insensitive_entry_and_absolute_offset(self):
        expected = b"synthetic A2 texture"
        bank = parse_gui_bank(make_gui_bank([(r"Art\GUI\Persistant\abyx.tex", expected)]))

        entry = bank[r"art\gui\persistant\abyx.tex"]

        self.assertEqual(bank.data[entry.offset : entry.offset + entry.length], expected)

    def test_gui_bank_parser_accepts_exact_directory_without_deflate_end_marker(self):
        expected = b"synthetic header directory"
        bank = parse_gui_bank(
            make_gui_bank([(r"Art\GUI\Persistant\abyx.tex", expected)], clean_deflate_end=False)
        )

        entry = bank[r"art\gui\persistant\abyx.tex"]

        self.assertEqual(bank.data[entry.offset : entry.offset + entry.length], expected)

    def test_sidecar_original_matches_current_qa_bank_payload_byte_for_byte(self):
        source = tiled_fixture(64, 64, {(0, 0): (255, 1, 2, 3)})
        bank_data = make_gui_bank([("Art\\GUI\\Persistant\\abyx.tex", source)])
        bank_entry = parse_gui_bank(bank_data)[r"art\gui\persistant\abyx.tex"]
        sidecar_entry = find_sidecar_entry(
            parse_sidecar(
                make_sidecar(
                    [("data/art/gui/gui_textures.bnk", bank_entry.offset, source, source)]
                )
            ),
            "data/art/gui/gui_textures.bnk",
            bank_entry.offset,
        )

        self.assertTrue(source_matches_sidecar(bank_data, bank_entry, sidecar_entry))
        changed = bytearray(bank_data)
        changed[bank_entry.offset + 5] ^= 1
        self.assertFalse(source_matches_sidecar(bytes(changed), bank_entry, sidecar_entry))

    def test_256_atlas_detiling_uses_atlas_pitch_across_tile_boundaries(self):
        atlas = tiled_fixture(
            64,
            64,
            {
                (0, 0): (255, 255, 0, 0),
                (32, 0): (255, 0, 255, 0),
                (0, 32): (255, 0, 0, 255),
                (63, 63): (255, 255, 255, 0),
            },
        )

        rgba = tiled_a2_to_rgba(atlas, 64, 64)

        self.assertEqual(rgba[0:4], bytes((255, 0, 0, 255)))
        self.assertEqual(rgba[(32 * 4) : (32 * 4 + 4)], bytes((0, 255, 0, 255)))
        self.assertEqual(rgba[((32 * 64) * 4) : ((32 * 64) * 4 + 4)], bytes((0, 0, 255, 255)))
        self.assertEqual(rgba[((63 * 64 + 63) * 4) : ((63 * 64 + 63) * 4 + 4)], bytes((255, 255, 0, 255)))

    def test_detiler_rejects_wrong_a2_size_header(self):
        payload = bytearray(tiled_fixture(64, 64, {}))
        struct.pack_into(">I", payload, 0, 1)

        with self.assertRaises(ValueError):
            tiled_a2_to_rgba(bytes(payload), 64, 64)


if __name__ == "__main__":
    unittest.main()
