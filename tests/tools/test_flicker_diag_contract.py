"""Round 20 outcome contract: the behavior-neutral [flicker-diag] logging was
added, used for one diagnostic run, and REMOVED after the diagnosis (no
permanent debug logs in production). The diagnostic verdict lives in
analysis-flicker-diagnostic.json.
"""
import hashlib
import json
from pathlib import Path

import unittest

ROOT = Path(r"D:\Fable.2.Game.of.the.Year.Edition-P2P\Fable-2-Recomp")
HEADER = ROOT / "src" / "core" / "fable2_fit_window_ui.h"
EV = Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FlickerDiagOutcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HEADER.is_file():
            cls.src = HEADER.read_text(encoding="utf-8", errors="ignore")

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_diag_removed_after_use(self):
        self.assertNotIn("[flicker-diag]", self.src)

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_toggle_logic_intact(self):
        self.assertIn("const bool now_playing = last != 0 && "
                      "detail::NowMs() - last < 300 && !menu_up;", self.src)

    @unittest.skipUnless((EV / "analysis-flicker-diagnostic.json").is_file(),
                         "diagnostic analysis not present")
    def test_verdict_recorded(self):
        report = json.loads((EV / "analysis-flicker-diagnostic.json").read_text(encoding="utf-8"))
        v = report["verdict"]
        c = report["correlation"]
        self.assertEqual(576, c["off_with_menu"])
        self.assertEqual(4, c["off_without_context"])
        self.assertIn("~1 Hz", c["reading"])
        self.assertIn("hysteresis", report["next_step_proposal"]["title"].lower())


if __name__ == "__main__":
    unittest.main()
