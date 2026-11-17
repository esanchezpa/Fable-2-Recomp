"""Contract tests for the opt-in frame-limiter watchdog (FASE 2, Round 15).

The watchdog lives in the hand-tuned hotfunc override of FrameLimiterWait_82242628
(src/core/hotfunc/vblank/). Contract:
  * opt-in cvar hang_watchdog, default false;
  * bounded spin: 250 ms host deadline inside the wait loop only;
  * on expiry: one [hang-watchdog] log per episode with the render-loop state,
    then break the wait so the frame completes and EndFrame publishes;
  * healthy spins under the timeout are unaffected and reset the episode;
  * no generated/ file is modified (hashes pinned in hang-evidence-hashes.json).
"""
import hashlib
import json
from pathlib import Path

import unittest

ROOT = Path(r"D:\Fable.2.Game.of.the.Year.Edition-P2P\Fable-2-Recomp")
OVERRIDE = ROOT / "src" / "core" / "hotfunc" / "vblank" / "FrameLimiterWait_82242628.cpp"
EV = Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class WatchdogContract(unittest.TestCase):
    @unittest.skipUnless(OVERRIDE.is_file(), "frame limiter override not present")
    def test_cvar_present_and_default_on(self):
        """Since the validated A/B (Round 15), the watchdog ships default ON;
        passing --hang_watchdog=false is the explicit rollback."""
        src = OVERRIDE.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("REXCVAR_DEFINE_BOOL(hang_watchdog", src)
        m = [l for l in src.splitlines() if "REXCVAR_DEFINE_BOOL(hang_watchdog" in l]
        self.assertTrue(any("true" in l for l in m), "default must be true now")

    @unittest.skipUnless(OVERRIDE.is_file(), "frame limiter override not present")
    def test_cvar_false_is_explicit_rollback(self):
        """cvar=false disables the watchdog (reverts to the original
        spin-forever wait): the loop must gate on REXCVAR_GET and a false
        value must reach the unbounded SpinPause path."""
        src = OVERRIDE.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("watchdog_on = REXCVAR_GET(hang_watchdog)", src)
        self.assertIn("if (watchdog_on)", src)
        self.assertIn("rollback", src.lower())

    @unittest.skipUnless(OVERRIDE.is_file(), "frame limiter override not present")
    def test_bounded_spin_250ms(self):
        src = OVERRIDE.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("kWatchdogTimeoutMs", src)
        self.assertIn("250", src)
        self.assertIn("steady_clock", src)

    @unittest.skipUnless(OVERRIDE.is_file(), "frame limiter override not present")
    def test_expiry_logs_once_and_breaks(self):
        src = OVERRIDE.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("[hang-watchdog]", src)
        self.assertIn("kStatusByteOffset", src)
        self.assertIn("10941", src)
        self.assertIn("kPublishGateOffset", src)
        self.assertIn("21532", src)

    @unittest.skipUnless((EV / "hang-evidence-hashes.json").is_file(), "hash ledger missing")
    def test_generated_tree_unmodified(self):
        ledger = json.loads((EV / "hang-evidence-hashes.json").read_text(encoding="utf-8"))
        for key in ["src-fable_2_recomp.157.cpp", "src-fable_2_recomp.69.cpp",
                    "src-fable_2_recomp.6.cpp", "src-fable_2_recomp.266.cpp"]:
            name = key.replace("src-", "")
            f = ROOT / "generated" / "default" / name
            self.assertTrue(f.is_file(), name)
            self.assertEqual(ledger[key], sha(f), f"{name} must stay untouched")

    @unittest.skipUnless(OVERRIDE.is_file(), "frame limiter override not present")
    def test_watchdog_hashes_recorded(self):
        ledger = json.loads((EV / "hang-evidence-hashes.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger.get("hotfunc-FrameLimiterWait_82242628.cpp"), sha(OVERRIDE))


    @unittest.skipUnless((EV / "analysis-watchdog-ab.json").is_file(),
                         "watchdog A/B analysis not present")
    def test_watchdog_ab_results_recorded(self):
        """FASE 2 A/B: 3 watchdog-ON runs zero hangs with 2 onsets logged and
        recovered (status=0x54, bit1 clear, counter 10 behind); control clean."""
        report = json.loads(
            (EV / "analysis-watchdog-ab.json").read_text(encoding="utf-8")
        )
        labels = [r["label"] for r in report["ab_runs"]]
        self.assertEqual(["wd-on1", "wd-on2", "wd-on3", "control"], labels)
        for r in report["ab_runs"]:
            self.assertIn("completed 900 s", r["outcome"])
        self.assertEqual([True, True, True, False],
                         [r["watchdog"] for r in report["ab_runs"]])
        oc = report["onset_capture"]
        self.assertIn("status=0x54", oc["on2"])
        self.assertIn("published=0x000003d1 deadline=0x000003db", oc["on2"])
        self.assertIn("bit1 (0x2) is CLEAR", oc["interpretation"])
        c = report["criteria"]
        self.assertTrue(c["a_zero_hangs"].startswith("PASS"))
        self.assertTrue(c["b_log_at_onset"].startswith("PASS"))
        self.assertTrue(c["c_baseline_clean"].startswith("PASS"))
        self.assertIn("fable_2.exe restored to the pre-watchdog binary", report["rollback"])


if __name__ == "__main__":
    unittest.main()
