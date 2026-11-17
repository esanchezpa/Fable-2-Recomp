"""Round 19 outcome contract: the letterbox hold grace was attempted and
REVERTED as ineffective (analysis-visual-flicker-fix.json).

Recorded facts:
  * the timed hold (grace 2000 and an explicit 9999 probe) did NOT remove the
    ended->started flashes (~0.5 s residual in every config, zero
    [fit-window-grace] logs at expiry);
  * the flash window sits right before the next clip's BinkOpen (game preload
    timing), which no silence-based timeout can cover;
  * it is unproven whether the letterbox state (vs the clip content cutting to
    black) is the visible artifact - one boundary screenshot attempt was
    inconclusive;
  * the runtime change was reverted; TickVideo is back to the original logic
    with a NOTE comment pointing at the analysis;
  * a context-based OFF (menu / UI-screen detection) is the proposed
    alternative and awaits approval.
"""
import hashlib
import json
from pathlib import Path

import unittest

ROOT = Path(r"D:\Fable.2.Game.of.the.Year.Edition-P2P\Fable-2-Recomp")
HEADER = ROOT / "src" / "core" / "fable2_fit_window_ui.h"
EV = Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class FlickerRound19Outcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HEADER.is_file():
            cls.src = HEADER.read_text(encoding="utf-8", errors="ignore")

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_grace_reverted_no_timed_hold(self):
        self.assertNotIn("fit_window_video_grace_ms", self.src)
        self.assertNotIn("[fit-window-grace]", self.src)
        self.assertIn("NOTE (Round 19", self.src)

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_original_logic_preserved(self):
        self.assertIn("const bool now_playing = last != 0 && "
                      "detail::NowMs() - last < 300 && !menu_up;", self.src)

    @unittest.skipUnless((EV / "analysis-visual-flicker-fix.json").is_file(),
                         "fix analysis not present")
    def test_ineffectiveness_and_alternative_recorded(self):
        report = json.loads((EV / "analysis-visual-flicker-fix.json").read_text(encoding="utf-8"))
        self.assertIn("DID NOT", report["outcome"]["verdict"])
        self.assertTrue(report["outcome"]["probe_9999"]["gaps_unchanged"])
        self.assertEqual(0, report["outcome"]["probe_9999"]["grace_logs"])
        self.assertIn("context-based", report["alternative_proposal"]["title"].lower())


if __name__ == "__main__":
    unittest.main()
