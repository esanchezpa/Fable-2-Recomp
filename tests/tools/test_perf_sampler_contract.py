"""Source-level guards for the QA-only Lua sampler integration.

These checks do not execute Lua; the gameplay RED/GREEN test remains the
runtime authority for Lua 5.1 behavior.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PerfSamplerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sampler = (ROOT / "src/lua/perfSampler.lua").read_text(encoding="utf-8")
        cls.f5 = (ROOT / "src/lua/F5.lua").read_text(encoding="utf-8")
        cls.console = (ROOT / "src/lua/console_cmds.lua").read_text(encoding="utf-8")
        cls.cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        cls.lua_test = (ROOT / "tests/lua/sampler_ring.lua").read_text(encoding="utf-8")

    def test_sampler_is_loaded_by_f5_before_update_can_tick(self):
        self.assertRegex(
            self.f5,
            re.compile(r'loadfile\("scripts/recomp/perfSampler\.lua"\)', re.I),
        )
        self.assertIn("sampler_state.tick()", self.f5)
        self.assertIn("sampler_state.tick_pending()", self.f5)
        self.assertIn("st.busy or st.show or not modal_is_clear", self.f5)
        self.assertIn("src/lua/*.lua", self.cmake)
        self.assertIn("tools/ensure_recomp_manifest.cmake", self.cmake)

    def test_ring_reports_overwrites_and_sampler_is_opt_in(self):
        self.assertIn("enabled = false", self.sampler)
        self.assertRegex(
            self.sampler,
            r"overwritten_value\s*=\s*[A-Za-z0-9_.]+\s*\+\s*1",
        )
        self.assertRegex(self.sampler, r"function\s+state\.dump\(\)[\s\S]*?overwritten")

    def test_console_exposes_start_stop_status_and_post_window_dump(self):
        self.assertRegex(self.console, r'add\("sampler"')
        for operation in ("request_start", "stop", "dump"):
            self.assertIn(f'sampler.{operation}', self.console)
        self.assertIn("DEFAULT_ARM_DELAY_FRAMES", self.sampler)
        self.assertNotIn("sampler.start(frames)", self.console)

    def test_sample_path_has_no_output_or_file_io(self):
        sample = re.search(
            r"state\.sample\s*=\s*function\(\)(.*?)\nend",
            self.sampler,
            re.S,
        )
        self.assertIsNotNone(sample)
        self.assertNotRegex(sample.group(1), r"\b(?:print|cprint|loadfile|io\.open)\s*\(")

    def test_in_game_sampler_test_restores_preexisting_runtime_state(self):
        self.assertIn("local original_state = {", self.lua_test)
        self.assertIn("ring_count = sampler.ring:count()", self.lua_test)
        self.assertIn("sampler.ring = original_state.ring", self.lua_test)
        self.assertIn("sampler.pending_frames = original_state.pending_frames", self.lua_test)
        self.assertIn("sampler.sampled = original_state.sampled", self.lua_test)


if __name__ == "__main__":
    unittest.main()
