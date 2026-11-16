"""Round 21 contract: letterbox toggle debounce (both transitions).

Root cause (analysis-flicker-diagnostic.json): the attract sequence flips the
desired letterbox state ~1.3x/s (video clips alternating with real menu
loads), and TickVideo applied every flip - 1160 toggles/~15 min = the visible
~1 Hz flicker. Fix: a toggle only happens after the desired state has
persisted `fit_window_debounce_ms` (default 800; 0 = old behavior); one
[fit-window-debounce] log per confirmed toggle.
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


class FlickerDebounceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HEADER.is_file():
            cls.src = HEADER.read_text(encoding="utf-8", errors="ignore")

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_cvar_defined_default_800(self):
        self.assertIn("REXCVAR_DEFINE_INT32(fit_window_debounce_ms", self.src)
        decl = [l for l in self.src.splitlines()
                if "REXCVAR_DEFINE_INT32(fit_window_debounce_ms" in l]
        self.assertTrue(any("800" in l for l in decl), "default must be 800")

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_both_directions_gated(self):
        # the pending-state tracking must gate the toggle before playing flips
        i = self.src.find("desired_since_ms")
        j = self.src.find("playing = now_playing;")
        k = self.src.find('SetFlagByName("present_letterbox"')
        self.assertTrue(0 < i < j < k, "debounce must sit before the flip and cvar write")

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_zero_disables(self):
        self.assertIn("debounce_ms > 0", self.src)

    @unittest.skipUnless(HEADER.is_file(), "fit window header not present")
    def test_log_once_per_confirmed_toggle(self):
        self.assertIn("[fit-window-debounce]", self.src)

    @unittest.skipUnless((EV / "hang-evidence-hashes.json").is_file(), "hash ledger missing")
    def test_header_hash_recorded(self):
        ledger = json.loads((EV / "hang-evidence-hashes.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger.get("src-fable2_fit_window_ui.h-debounce"), sha(HEADER))

    @unittest.skipUnless((EV / "analysis-flicker-debounce.json").is_file(),
                         "debounce A/B analysis not present")
    def test_ab_results_recorded(self):
        report = json.loads((EV / "analysis-flicker-debounce.json").read_text(encoding="utf-8"))
        labels = [r["label"].split(" ")[0] for r in report["ab_runs"]]
        self.assertEqual(["db-on1", "db-on2", "control"], labels)
        for r in report["ab_runs"]:
            self.assertIn("completed 900 s", r["outcome"])
        self.assertEqual([2, 2, 2], [r["toggles"] for r in report["ab_runs"]])
        self.assertEqual([2, 2, 0], [r["debounce_logs"] for r in report["ab_runs"]])
        a = report["criteria"]
        self.assertTrue(a["a_toggle_reduction"].startswith("PASS"))
        self.assertTrue(a["a_toggle_reduction"].endswith("baseline 1160 toggles/~15 min under the same attract conditions"))
        self.assertTrue(a["c_no_side_effects"].startswith("PASS"))
        self.assertIn("40/40", report["guardrails"]["saves"])
        self.assertIn("Cancelar", report["incident"]["response"])


if __name__ == "__main__":
    unittest.main()
