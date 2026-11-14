"""Tests for the shader pre-build list format and validation helpers."""
from pathlib import Path

import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "shader_prebuild_list", ROOT / "tools" / "shader_prebuild_list.py"
)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

parse_list = module.parse_list
validate_structure = module.validate_structure
source_summary = module.source_summary
unique_shader_hashes = module.unique_shader_hashes
HEADER_SIZE = module.HEADER_SIZE
RECORD_SIZE = module.RECORD_SIZE
TITLE_ID = module.TITLE_ID
XEX_BASE = module.XEX_BASE

SAMPLE = """fable2-shader-prebuild 1
title 4D5307F1
xsh-header 5845534820201219
xpso-header 584550534458525420260226
shader 1E6883FCCDE1F688 0000001B xex 82095DD8
shader A4A965C189287B99 80000009 bank data/Shaders/ShadersRelease.sbk 21 636
shader BD2477FEDE6BEAB1 0000001B bank data/Shaders/ShadersRelease.sbk 19 2340 9:20000000 10:00393000
pipeline """ + ("00" * RECORD_SIZE) + """
"""


class ShaderPrebuildListTests(unittest.TestCase):
    def test_parses_minimal_valid_list(self):
        parsed = parse_list(SAMPLE)
        self.assertEqual(parsed.format, 1)
        self.assertEqual(parsed.title, TITLE_ID)
        self.assertEqual(len(parsed.xsh_header), HEADER_SIZE)
        self.assertEqual(len(parsed.xpso_header), 12)
        self.assertEqual(len(parsed.shaders), 3)
        self.assertEqual(len(parsed.pipelines), 1)
        self.assertEqual(len(parsed.pipelines[0]), RECORD_SIZE)

    def test_tracks_shader_sources_and_patches(self):
        parsed = parse_list(SAMPLE)
        self.assertEqual(parsed.shaders[0].source, "xex")
        self.assertEqual(parsed.shaders[0].xex_address, 0x82095DD8)
        self.assertEqual(parsed.shaders[0].offset, 0x82095DD8 - XEX_BASE)
        self.assertEqual(parsed.shaders[1].source, "bank")
        self.assertEqual(parsed.shaders[1].bank, "data/Shaders/ShadersRelease.sbk")
        self.assertEqual(parsed.shaders[1].entry, 21)
        self.assertEqual(parsed.shaders[1].offset, 636)
        self.assertEqual(parsed.shaders[2].patches, ((9, 0x20000000), (10, 0x00393000)))

    def test_source_summary_and_unique_hashes(self):
        parsed = parse_list(SAMPLE)
        self.assertEqual(source_summary(parsed), {"xex": 1, "bank": 2})
        self.assertEqual(len(unique_shader_hashes(parsed)), 3)

    def test_validation_accepts_minimal_list(self):
        parsed = parse_list(SAMPLE)
        self.assertEqual(validate_structure(parsed), [])

    def test_rejects_missing_headers(self):
        text = SAMPLE.replace("xsh-header 5845534820201219\n", "")
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_bad_pipeline_size(self):
        text = SAMPLE.replace("00" * RECORD_SIZE, "00" * (RECORD_SIZE - 1))
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_unknown_source(self):
        text = SAMPLE.replace("xex 82095DD8", "gpu 82095DD8")
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_bad_patch(self):
        text = SAMPLE.replace("9:20000000", "9")
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_wrong_title(self):
        text = SAMPLE.replace(TITLE_ID, "00000000")
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_xex_address_below_base(self):
        text = SAMPLE.replace("82095DD8", "81000000")
        with self.assertRaises(ValueError):
            parse_list(text)

    def test_rejects_duplicate_shader_hash(self):
        text = SAMPLE.replace("A4A965C189287B99", "1E6883FCCDE1F688")
        parsed = parse_list(text)
        self.assertTrue(any("duplicate shader hash" in error for error in validate_structure(parsed)))

    def test_rejects_empty_sections(self):
        text = "fable2-shader-prebuild 1\ntitle " + TITLE_ID + "\nxsh-header 5845534820201219\nxpso-header 584550534458525420260226\n"
        with self.assertRaises(ValueError):
            parse_list(text)


if __name__ == "__main__":
    unittest.main()
