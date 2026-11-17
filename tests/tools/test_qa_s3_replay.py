import importlib.util
import csv
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "qa_s3_replay.py"
SPEC = importlib.util.spec_from_file_location("qa_s3_replay", MODULE_PATH)
replay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replay
SPEC.loader.exec_module(replay)


class ReplayPlanTests(unittest.TestCase):
    def test_180_second_pass_is_moving_camera_cycle_with_short_observable_steps(self):
        plan = replay.build_replay_plan(180)

        self.assertEqual(plan["duration_seconds"], 180)
        self.assertAlmostEqual(sum(action["duration_seconds"] for action in plan["actions"]), 180, places=9)
        self.assertTrue(all(action["duration_seconds"] <= replay.MAX_ACTION_SECONDS
                            for action in plan["actions"]))
        self.assertTrue(all(action["observe_before"] for action in plan["actions"]))
        self.assertTrue(all(action["observe_after"] for action in plan["actions"]))
        self.assertIn("sprint_forward", {action["kind"] for action in plan["actions"]})
        self.assertIn("reorient_left_back", {action["kind"] for action in plan["actions"]})
        self.assertIn("reorient_right_back", {action["kind"] for action in plan["actions"]})
        self.assertIn("camera_sweep", {action["kind"] for action in plan["actions"]})
        controls = {action["kind"]: action["controls"] for action in plan["actions"]}
        self.assertEqual(controls["reorient_left_back"], ["a", "s"])
        self.assertEqual(controls["reorient_right_back"], ["d", "s"])
        camera_actions = [action for action in plan["actions"] if action["kind"] == "camera_sweep"]
        self.assertEqual(len(camera_actions) % 4, 0)
        self.assertTrue(all(action["controls"] == ["mouse_delta", 500, 0]
                            for action in camera_actions))

    def test_pass_shorter_than_plan_gate_is_rejected(self):
        with self.assertRaises(ValueError):
            replay.build_replay_plan(179)

    def test_qpc_markers_append_to_new_file_and_preserve_qpc_units(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "markers.jsonl"
            replay.append_qpc_marker(path, "pass_start", qpc=123456, frequency=10_000_000)
            replay.append_qpc_marker(path, "pass_end", qpc=1_923_456_789, frequency=10_000_000)

            markers = [replay.json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([marker["qpc"] for marker in markers], [123456, 1_923_456_789])
            self.assertEqual([marker["frequency"] for marker in markers], [10_000_000, 10_000_000])
            self.assertEqual([marker["name"] for marker in markers], ["pass_start", "pass_end"])

    def test_marker_file_creation_never_overwrites_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "markers.jsonl"
            path.write_text("existing evidence\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                replay.append_qpc_marker(path, "pass_start", qpc=1, frequency=10)

            self.assertEqual(path.read_text(encoding="utf-8"), "existing evidence\n")

    def test_trace_summary_counts_only_rows_inside_qpc_window_without_claiming_fps(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                stream.write("# clock=qpc,frequency=10000000\n")
                writer = csv.writer(stream)
                writer.writerow(["event", "event_sequence", "clock_ticks", "guest_output_id",
                                 "mailbox_index", "swapchain_present_count", "result"])
                writer.writerow(["guest_output_produced", 1, 100, 1, 2, 0, 0])
                writer.writerow(["guest_output_produced", 2, 150, 2, 3, 0, 0])
                writer.writerow(["dxgi_present_attempt", 3, 200, 0, -1, 1, 0])

            summary = replay.summarize_trace(path, 100, 150)

            self.assertEqual(summary["duration_seconds"], 0.000005)
            self.assertEqual(summary["event_rows"], 2)
            self.assertEqual(summary["event_counts"], {"guest_output_produced": 2})
            self.assertEqual(summary["unique_nonzero_guest_output_ids_produced"], 2)
            self.assertIn("No content uniqueness", summary["interpretation_limit"])

    def test_trace_summary_rejects_nonpositive_qpc_frequency(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid-trace.csv"
            path.write_text(
                "# clock=qpc,frequency=0\n"
                "event,event_sequence,clock_ticks,guest_output_id,mailbox_index,swapchain_present_count,result\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                replay.summarize_trace(path, 1, 2)

    def test_trace_summary_tracks_mailbox_ids_reuse_unobserved_outputs_intervals_and_gaps(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mailbox-trace.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                stream.write("# clock=qpc,frequency=1000\n")
                writer = csv.writer(stream)
                writer.writerow(["event", "event_sequence", "clock_ticks", "guest_output_id",
                                 "mailbox_index", "swapchain_present_count", "result"])
                # Output 1 is replaced before acquisition; output 2 is consumed and
                # presented repeatedly; output 4 is acquired but not presented; 5
                # is a trailing output not observed by the consumer.
                writer.writerow(["guest_output_produced", 1, 100, 1, 0, -1, 0])
                writer.writerow(["guest_output_produced", 2, 110, 2, 1, -1, 0])
                writer.writerow(["guest_output_acquired", 1, 120, 2, 1, -1, 0])
                writer.writerow(["dxgi_present_attempt", 1, 130, 2, 1, 7, 0])
                writer.writerow(["guest_output_acquired", 2, 140, 2, 1, -1, 0])
                writer.writerow(["dxgi_present_attempt", 2, 150, 2, 1, 8, 0])
                writer.writerow(["guest_output_produced", 4, 200, 4, 2, -1, 0])
                writer.writerow(["guest_output_acquired", 4, 210, 4, 2, -1, 0])
                writer.writerow(["guest_output_produced", 5, 250, 5, 0, -1, 0])

            summary = replay.summarize_trace(path, 100, 250)

            self.assertEqual(summary["output_production_events"], 4)
            self.assertEqual(summary["distinct_output_ids_produced"], 4)
            self.assertEqual(summary["output_acquisition_events"], 3)
            self.assertEqual(summary["distinct_output_ids_acquired"], 2)
            self.assertEqual(summary["present_attempts"], 2)
            self.assertEqual(summary["distinct_output_ids_in_present_attempts"], 1)
            self.assertEqual(summary["production_id_reuse_events"], 0)
            self.assertEqual(summary["acquisition_reuse_events"], 1)
            self.assertEqual(summary["present_reuse_events"], 1)
            self.assertEqual(summary["produced_ids_not_acquired_in_window"], 2)
            self.assertEqual(summary["acquired_ids_not_presented_in_window"], 1)
            self.assertEqual(summary["sequence_missing_rows_by_event"], {
                "guest_output_acquired": 1,
                "guest_output_produced": 1,
            })
            self.assertEqual(summary["intervals_seconds"]["guest_output_produced"]["max"], 0.09)
            self.assertEqual(summary["intervals_seconds"]["guest_output_acquired"]["mean"], 0.045)
            self.assertFalse(summary["claims_unique_guest_frames"])
            self.assertFalse(summary["claims_scanout"])

    def test_trace_summary_rejects_files_and_row_counts_over_bounded_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bounded-trace.csv"
            path.write_text(
                "# clock=qpc,frequency=1000\n"
                "event,event_sequence,clock_ticks,guest_output_id,mailbox_index,swapchain_present_count,result\n"
                "guest_output_produced,1,100,1,0,-1,0\n"
                "guest_output_produced,2,110,2,1,-1,0\n",
                encoding="utf-8",
            )
            original_bytes = replay.MAX_TRACE_BYTES
            original_rows = replay.MAX_TRACE_ROWS
            try:
                replay.MAX_TRACE_BYTES = path.stat().st_size - 1
                with self.assertRaisesRegex(ValueError, "byte limit"):
                    replay.summarize_trace(path, 0, 200)
                replay.MAX_TRACE_BYTES = original_bytes
                replay.MAX_TRACE_ROWS = 1
                with self.assertRaisesRegex(ValueError, "row limit"):
                    replay.summarize_trace(path, 0, 200)
            finally:
                replay.MAX_TRACE_BYTES = original_bytes
                replay.MAX_TRACE_ROWS = original_rows


if __name__ == "__main__":
    unittest.main()
