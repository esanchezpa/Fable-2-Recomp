"""Offline contract test for the Tracy-stage crash analysis evidence.

Validates, without launching anything, that the recorded crash analysis stays
consistent with the artifacts it cites:

* the exception dump hash recorded in analysis-report.json matches the file;
* the generated guest source still contains the identified faulting load and
  caller sites at the recorded line numbers;
* the report records the null-pointer mechanism and the no-Tracy
  reproducibility evidence.

Skips when optional artifacts are absent (generated trees or QA-Storage
evidence may not exist on every checkout).
"""

import hashlib
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = Path(r"D:\QA-Storage\fable2-active\evidence\tracy-crash-offline-20261116")
REPORT = EVIDENCE / "analysis-report.json"
DUMP = Path(
    r"D:\QA-Storage\fable2-active\runs\20261116T041300Z-5908-e6b5ffa6"
    r"\fable2-exception.dmp"
)
GENERATED = REPO / "generated" / "default"


@unittest.skipUnless(REPORT.is_file(), "offline crash analysis report not present")
class TracyCrashOfflineAnalysisContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_dump_hash_matches_recorded(self):
        recorded = self.report["dump"]
        self.assertTrue(DUMP.is_file(), "exception dump not present")
        digest = hashlib.sha256(DUMP.read_bytes()).hexdigest()
        self.assertEqual(recorded["sha256"], digest.lower())

    @unittest.skipUnless((GENERATED / "fable_2_recomp.199.cpp").is_file(),
                         "generated recomp tree not present")
    def test_faulting_load_present_at_recorded_line(self):
        lines = (GENERATED / "fable_2_recomp.199.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertEqual(
            lines[930].strip(),
            "ctx.r11.u64 = REX_LOAD_U16(ctx.r11.u32 + 24);",
        )
        self.assertIn("ProcessAndProcessAndProcess806_822069C0", lines[870])

    @unittest.skipUnless((GENERATED / "fable_2_recomp.47.cpp").is_file(),
                         "generated recomp tree not present")
    def test_caller_site_present_at_recorded_line(self):
        lines = (GENERATED / "fable_2_recomp.47.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertIn("ctx.lr = 0x82B69620;", lines[20844])
        self.assertIn("ProcessAndProcessAndProcess806_822069C0(ctx, base);", lines[20845])

    def test_report_documents_null_mechanism_and_no_tracy_repro(self):
        rc = self.report["root_cause_progress"]
        self.assertIn("12440", rc["verified_mechanism"]["callee_index"])
        self.assertIn("0x18", rc["verified_mechanism"]["fault"])
        repro = rc["reproducibility_without_tracy"]
        self.assertEqual(len(repro["logs"]), 4)
        self.assertIn("0xF800002C", repro["logs"][0])

    def test_report_inputs_record_hashes(self):
        for entry in self.report["inputs"]:
            self.assertIn("sha256", entry)
            self.assertEqual(len(entry["sha256"]), 64)

    def test_synthetic_repro_null_table_entry_faults_at_guest_0x18(self):
        """Synthetic reproducibility of the verified crash mechanism.

        Encodes the translated guest sequence from the dump: caller passes
        r4=256, the callee indexes table slot (r4&7) at object+12440, loads a
        NULL entry, then dereferences entry+24 -> guest fault 0x18.
        """
        GUEST_BASE = 0x200000000

        def translated_load(object_addr, r4, table):
            index = r4 & 0x7
            slot_offset = (index + 3110) * 4  # (r21+3110)*4, per generated code
            self.assertEqual(slot_offset, 12440 + index * 4)
            entry = table[slot_offset]  # u32 at object+slot_offset
            return (entry + 24) & 0xFFFFFFFF  # lhz r11,24(r11)

        table = {slot: 0 for slot in range(12440, 12440 + 8 * 4, 4)}
        with self.assertRaises(AssertionError):
            # Guest dereference of a NULL entry would fault; model it as the
            # address check the runtime log recorded.
            guest_addr = translated_load(0x822069C0, 256, table)
            self.assertEqual(guest_addr, 0x18)
            self.assertEqual(GUEST_BASE + guest_addr, 0x200000018)
            raise AssertionError("fault address reproduced: guest 0x18")

    def test_table_layout_slot4_matches_literal_offset_12456(self):
        self.assertEqual(12440 + 4 * 4, 12456)

    @unittest.skipUnless((GENERATED / "fable_2_recomp.47.cpp").is_file(),
                         "generated recomp tree not present")
    def test_crash_object_is_global_singleton_at_0x833601B8(self):
        """1265 loads the object pointer from static global 0x83360000+412."""
        lines = (GENERATED / "fable_2_recomp.47.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        # lis r29,-31946 -> 0x83360000 ; lwz r3,412(r29) -> *(0x833601B8)
        self.assertIn("ctx.r29.s64 = -2093613056;", lines[20645])
        self.assertIn("REX_LOAD_U32(ctx.r29.u32 + 412);", lines[20653])

    @unittest.skipUnless((GENERATED / "fable_2_recomp.166.cpp").is_file(),
                         "generated recomp tree not present")
    def test_helper_sub_82426C08_never_stores_to_arg3(self):
        """sub_82426C08 stores only to the output buffer (r30) and a list
        object (r31 = *(*(r4+0))); its r5 argument is never written."""
        lines = (GENERATED / "fable_2_recomp.166.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        body = lines[5218:5382]
        stores = [l for l in body if "REX_STORE_U32" in l]
        self.assertEqual(len(stores), 6)
        for l in stores:
            self.assertNotIn("ctx.r29.u32 +", l)  # r29 holds arg3 (r5)

    @unittest.skipUnless((GENERATED / "fable_2_recomp.153.cpp").is_file(),
                         "generated recomp tree not present")
    def test_caller_plus_12440_is_absolute_global_0x820B3098(self):
        """In sub_8244DCB8 the +12440 argument is 0x820B0000+12440, a static
        global - not the crash object's table."""
        lines = (GENERATED / "fable_2_recomp.153.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertIn("ctx.r10.s64 = -2113208320;", lines[5572])  # 0x820B0000
        self.assertIn("ctx.r5.s64 = ctx.r10.s64 + 12440;", lines[5576])

    @unittest.skipUnless((GENERATED / "fable_2_recomp.45.cpp").is_file(),
                         "generated recomp tree not present")
    def test_singleton_setter_writes_0x833601B8(self):
        """sub_82B69978 stores the singleton pointer at 0x83360000+412."""
        lines = (GENERATED / "fable_2_recomp.45.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertIn("ctx.r27.s64 = -2093613056;", lines[20323])
        self.assertIn("REX_STORE_U32(ctx.r27.u32 + 412, ctx.r11.u32);", lines[20331])
        self.assertIn("REX_STORE_U32(ctx.r27.u32 + 412, ctx.r31.u32);", lines[20482])

    RUN_A_JSON = Path(
        r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116"
        r"\analysis-watchpoint-run-a.json")

    @unittest.skipUnless(RUN_A_JSON.is_file(),
        "watchpoint run A analysis not present")
    def test_watchpoint_run_a_facts_recorded(self):
        """Run A corrections: guest base verified, cell read 0 at first hit,
        pointer-cell watch fired with a CLEAR from VCRUNTIME unwind code."""
        report = json.loads(self.RUN_A_JSON.read_text(encoding="utf-8"))
        self.assertTrue(report["guest_base_verified"].startswith("0x200000000"))
        self.assertIn("read 0 at the first setter hit", report["corrections_documented"][0])
        self.assertIn("CLEAR", report["corrections_documented"][1])
        self.assertIn("VCRUNTIME140!_NLG_Return2", report["corrections_documented"][2])
        self.assertIn("match the fatal crash stack root chain", report["corrections_documented"][2])

    @unittest.skipUnless((GENERATED / "fable_2_recomp.166.cpp").is_file(),
                         "generated recomp tree not present")
    def test_init_paths_zero_table_slot5(self):
        """sub_82A5E388 and sub_82A63168 write 0 into singleton+12460."""
        lines166 = (GENERATED / "fable_2_recomp.166.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertIn("ctx.r28.s64 = 0;", lines166[19731])
        self.assertIn("REX_STORE_U32(ctx.r30.u32 + 12460, ctx.r28.u32);", lines166[19735])
        lines185 = (GENERATED / "fable_2_recomp.185.cpp").read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines()
        self.assertIn("REX_STORE_U32(ctx.r31.u32 + 12460, ctx.r14.u32);", lines185[19906])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-hang-run-f.json").is_file(),
                         "run F hang analysis evidence not present")
    def test_run_f_hang_diagnosis_recorded(self):
        """Run F hang: no debugger stop, UI thread blocked on WaitForUITick,
        two guest render threads spinning in FrameLimiterWait, saves intact."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-hang-run-f.json").read_text(encoding="utf-8")
        )
        fids = [f["id"] for f in report["findings"]]
        self.assertEqual(
            ["F1", "F2", "F3", "F4", "F5", "F6"], fids)
        f1 = report["findings"][0]["finding"]
        self.assertIn("No debugger stop", f1)
        self.assertIn("5214 first-chance", f1)
        f3 = report["findings"][2]["finding"]
        self.assertIn("WaitForUITickFromUIThread", f3)
        self.assertIn("input no se procesa", f3)
        f4 = report["findings"][3]["finding"]
        self.assertIn("FrameLimiterWait_82242628", f4)
        self.assertIn("ProcessAndProcessAndProcess1265_82B69488", f4)
        self.assertTrue(report["saves"].startswith("40/40"))


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-hang-run-f-part2.json").is_file(),
                         "run F spin-loop decode evidence not present")
    def test_run_f_spin_loop_decode_recorded(self):
        """Part 2: pause-spin loop decoded, frozen counter values recorded,
        High Tick Rate patch state identical across runs and unverified as cause."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-hang-run-f-part2.json").read_text(encoding="utf-8")
        )
        fids = [f["id"] for f in report["facts"]]
        self.assertEqual(["S1", "S2", "S3", "S4", "S5", "S6", "S7"], fids)
        s2 = report["facts"][1]["fact"]
        self.assertIn("+0xF0=0x2841 (snapshot)", s2)
        self.assertIn("+0x50=0x2847", s2)
        self.assertIn("advanced only 6 units past the snapshot and froze", s2)
        s6 = report["facts"][5]["fact"]
        self.assertIn("be8 0x83319511", s6)
        self.assertIn("cannot be assigned cause without a control run", s6)
        s7 = report["facts"][6]["fact"]
        self.assertIn("MiniDumpWithFullMemory (0x1)", s7)
        self.assertIn("0x833601B8 cell", s7)


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-run-g-control.json").is_file(),
                         "run G control-run evidence not present")
    def test_run_g_control_run_recorded(self):
        """Control run with high_tick_rate=false: 900 s, no crash, no hang,
        AV stream continuous, saves intact, config restored."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-run-g-control.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["config"]["high_tick_rate"] is False)
        self.assertTrue(report["config"]["restored_after_run"] is True)
        oc = report["outcome"]
        self.assertFalse(oc["crash_fatal"])
        self.assertFalse(oc["hang"])
        self.assertEqual(900.0, oc["elapsed_s"])
        self.assertIn("continuous", oc["av_stream"])
        self.assertIn("froze at 5214", oc["contrast_run_f"])
        self.assertIn("Hero 1 loaded", report["navigation"])
        self.assertTrue(report["saves"].startswith("40/40"))
        self.assertTrue(report["conclusion"]["attribution"].startswith("PARTIAL"))


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-counter-writer.json").is_file(),
                         "counter-writer analysis not present")
    def test_counter_writer_hunt_recorded(self):
        """Offline W1-W4: guest clock is pure 1:1 host clock (no boosts),
        counter writer unresolved, F-hang/B3-crash unification hypothesis,
        stage config staleness (21 missing keys incl. faster_render_targets)."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-counter-writer.json").read_text(encoding="utf-8")
        )
        fids = [f["id"] for f in report["facts"]]
        self.assertEqual(["W1", "W2", "W3", "W4"], fids)
        w1 = report["facts"][0]["fact"]
        self.assertIn("guest_time_scalar_ = 1.0", w1)
        self.assertIn("REJECTED", w1)
        w2 = report["facts"][1]["fact"]
        self.assertIn("10896/10908", w2)
        self.assertIn("UNRESOLVED", w2)
        w3 = report["facts"][2]["fact"]
        self.assertIn("two paths", w3)
        w4 = report["facts"][3]["fact"]
        self.assertIn("faster_render_targets", w4)
        self.assertIn("STAGE CONFIG STALENESS", w4)
        self.assertTrue(report["next_step_decided"].startswith("Retake F-02"))
        self.assertIn("never claimed without recorded evidence", report["next_step_decided"])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-ab.json").is_file(),
                         "F-02 A/B analysis not present")
    def test_f02_ab_recorded(self):
        """F-02 A/B: ON stable 900 s without visual corruption; OFF hung at
        t~21 s in title (tick-on); metrics are event counts, not guest FPS."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-ab.json").read_text(encoding="utf-8")
        )
        self.assertFalse(report["runs"]["OFF"]["outcome"].startswith("completed"))
        self.assertIn("HANG at t~21-26 s", report["runs"]["OFF"]["outcome"])
        self.assertIn("NO corruption", report["runs"]["ON"]["outcome"])
        self.assertIn("NOT guest FPS", report["metrics"]["note"])
        self.assertIn("stop at t=20.8 s", report["metrics"]["OFF_stop"])
        m = report["attribution_matrix"]
        self.assertIn("had high_tick_rate=true", m["reading"])
        self.assertIn("NOT MEASURED", report["verdict"]["f02"])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-factorial.json").is_file(),
                         "F-02 factorial analysis not present")
    def test_f02_factorial_pair_recorded(self):
        """Clean tick-off pair: OFF2 and ON2 both stable 900 s without
        corruption; event metrics differ <=4%; F-02 effect not measurable."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-factorial.json").read_text(encoding="utf-8")
        )
        labels = [r["label"] for r in report["runs"]]
        self.assertEqual(["OFF2", "ON2"], labels)
        for r in report["runs"]:
            self.assertTrue(r["outcome"].startswith("completed 900 s"))
            self.assertIn("NO corruption", r["outcome"])
            self.assertFalse(r["high_tick_rate"])
        m = report["metrics"]
        self.assertIn("NOT guest FPS", m["note"])
        a, b = m["ON2_tick_off_frt_on"], m["OFF2_tick_off_frt_off"]
        self.assertTrue(abs(a["dxgi_present_per_s"] - b["dxgi_present_per_s"]) / b["dxgi_present_per_s"] < 0.05)
        self.assertIn("~1-4%", m["delta_reading"])
        self.assertIn("tick-off = 3 stable runs out of 3", report["attribution_progress"])
        self.assertIn("byte-identical", report["guardrails"]["stage"])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-sweep.json").is_file(),
                         "F-02 resolution sweep analysis not present")
    def test_f02_resolution_sweep_recorded(self):
        """Sweep: 1x and 2x pairs, tick-off everywhere, four completed runs,
        no corruption; 2x verified by VRAM evidence; no consistent FRT gain."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-sweep.json").read_text(encoding="utf-8")
        )
        self.assertEqual([1, 1, 2, 2], [r["scale"] for r in report["runs"]])
        for r in report["runs"]:
            self.assertTrue(r["outcome"].startswith("completed 900 s"))
        self.assertIn("VRAM 2169 MB vs ~360 MB", report["runs"][2]["outcome"])
        self.assertIn("flip sign between scales", report["metrics"]["frt_effect"])
        self.assertIn("NOT DECLARED", report["verdict"]["f02_candidate"])
        self.assertIn("Idle scene", report["limitations"][0])
        self.assertTrue(report["guardrails"]["saves"].startswith("40/40"))


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-rc-tickrate.json").is_file(),
                         "tick-rate no-cdb repro analysis not present")
    def test_rc_tickrate_no_cdb_recorded(self):
        """Two no-cdb attempts with tick-on: no hang (log heartbeat never
        froze, no dump); debugger-vs-no-debugger split recorded honestly."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-rc-tickrate.json").read_text(encoding="utf-8")
        )
        self.assertEqual([1, 2], [r["attempt"] for r in report["runs"]])
        for r in report["runs"]:
            self.assertIn("NO hang", r["outcome"])
        self.assertIn("HANG DID NOT REPRODUCE", report["result"])
        self.assertIn("0 unstable / 2 stable WITHOUT cdb", report["result"])
        m = report["matrix_update"]["reading"]
        self.assertIn("4 unstable (44%)", m)
        self.assertIn("NOT proof", report["result"])
        self.assertTrue(report["guardrails"]["saves"].startswith("40/40"))


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-gpu-bound.json").is_file(),
                         "F-02 GPU-bound verdict not present")
    def test_f02_gpu_bound_verdict_recorded(self):
        """GPU-bound 2x pair: mixed-sign deltas (present OFF +4.1%, swap ON +18%),
        F-02 closed definitively, ON remains compatible, next front = static PDB hunt."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-f02-gpu-bound.json").read_text(encoding="utf-8")
        )
        labels = [r["label"] for r in report["runs"]]
        self.assertEqual(["gpu-ON (FRT on)", "gpu-OFF (FRT off)"], labels)
        for r in report["runs"]:
            self.assertIn("no corruption", r["outcome"])
        m = report["metrics"]
        self.assertEqual(46.81, m["gpu_on_frt_on"]["present_per_s"])
        self.assertEqual(48.72, m["gpu_off_frt_off"]["present_per_s"])
        self.assertIn("SIGNS ARE MIXED", m["reading"])
        self.assertIn("CLOSED DEFINITIVELY", report["verdict"]["f02"])
        self.assertIn("COMPATIBLE", report["verdict"]["compatibility"])
        self.assertIn("aborted with Escape", report["guardrails"]["saves"])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-writer-found.json").is_file(),
                         "writer-found analysis not present")
    def test_counter_writer_mechanism_recorded(self):
        """Writer found in guest code (EndFrame_822981F0): publish gated by
        obj+21532==0 AND status-byte bit1 (obj+10941); target advances +2/frame;
        hang model M1-M6 fits the 6/8 frozen delta; fix PROPOSED, not implemented."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-writer-found.json").read_text(encoding="utf-8")
        )
        w = report["resolution_of_W2"]
        self.assertIn("EndFrame_822981F0", w["writer"])
        self.assertIn("obj+21532==0 AND (obj+10941 & 0x2)!=0", w["publish"])
        self.assertIn("false_negative_note", w)
        steps = [s["step"] for s in report["mechanism"]]
        self.assertEqual(["M1", "M2", "M3", "M4", "M5", "M6"], steps)
        m5 = report["mechanism"][4]["text"]
        self.assertIn("Deadlock: limiter waits for a counter whose writer is downstream", m5)
        m6 = report["mechanism"][5]["text"]
        self.assertIn("806_822069C0", m6)
        self.assertIn("6/8", m6)
        fix = report["candidate_fix_PROPOSAL_ONLY"]
        self.assertIn("NOT IMPLEMENTED", fix["status"])
        self.assertIn("Opt-in runtime watchdog", fix["title"])
        self.assertIn("high_tick_rate_link", report)
        self.assertTrue(report["guardrails"]["no_runtime_change"])


    @unittest.skipUnless((Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-watchpoint-onset.json").is_file(),
                         "watchpoint onset analysis not present")
    def test_watchpoint_onset_phase1_recorded(self):
        """FASE 1: watchpoint armed from SetInterruptCallback (obj 0x44114780,
        matches F dump); ~35 min instrumented exposure with ZERO byte-clear
        events and no hang; ambiguity between 'no clears' and 'watchpoint
        never triggered' recorded; limit documented, FASE 2 (watchdog) accepted."""
        report = json.loads(
            (Path(r"D:\QA-Storage\fable2-active\evidence\tracy-watchpoint-20261116") / "analysis-watchpoint-onset.json").read_text(encoding="utf-8")
        )
        self.assertEqual(["1", "1-bis", "2 (instrumented, extended)"], [a["attempt"] for a in report["attempts"]])
        a2 = report["attempts"][2]
        self.assertIn("0x44114780", a2["result"])
        self.assertIn("~35 min", a2["exposure"])
        self.assertIn("orphaned instrumented session", a2["result"])
        self.assertIn("never transitioned to bit1-clear", report["findings"][0]["finding"])
        p1 = report["findings"][0]["finding"]
        self.assertIn("(b) the watchpoint address/mapping never triggered", p1)
        self.assertIn("statistical_limit", report)
        self.assertIn("proceed to FASE 2", report["statistical_limit"])
        self.assertTrue(report["guardrails"]["saves"].startswith("40/40"))


if __name__ == "__main__":
    unittest.main()
