import importlib.util
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = ROOT / "tools" / "qa_storage_guard.py"
SPEC = importlib.util.spec_from_file_location("qa_storage_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)


class StoragePolicyTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_managed_storage_counts_rexglue_sdk_build_output(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            base = Path(temporary)
            repository = base / "repo"
            sdk_output = repository / "thirdparty" / "rexglue-sdk" / "out"
            managed = base / "managed"
            sdk_output.mkdir(parents=True)
            managed.mkdir()
            (sdk_output / "runtime.lib").write_bytes(b"sdk output")
            (managed / "evidence.csv").write_bytes(b"managed evidence")

            self.assertEqual(
                guard.managed_storage_bytes(managed, repository),
                len(b"sdk output") + len(b"managed evidence"),
            )

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_gameplay_launch_targets_only_managed_copy_and_selects_backend(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            game_root = Path(temporary) / "game-copy"
            game_root.mkdir()
            exe = game_root / "fable_2.exe"
            exe.write_bytes(b"test fixture")
            self.assertEqual(guard.gameplay_command(game_root, "d3d12"),
                             [str(exe.resolve()), "--gpu_plugin=xenos"])
            self.assertEqual(guard.gameplay_command(game_root, "vulkan"),
                             [str(exe.resolve()), "--gpu_plugin=xenos-vulkan"])
            with self.assertRaises(guard.GuardError):
                guard.gameplay_command(ROOT, "d3d12")

    def test_preflight_rejects_c_below_start_threshold(self):
        result = guard.check_capacity(
            c_free=guard.GIB * 29,
            d_free=guard.GIB * 200,
            managed_bytes=0,
            phase="start",
        )
        self.assertIn("C:", result)

    def test_preflight_rejects_d_below_start_threshold(self):
        result = guard.check_capacity(
            c_free=guard.GIB * 100,
            d_free=guard.GIB * 99,
            managed_bytes=0,
            phase="start",
        )
        self.assertIn("D:", result)

    def test_runtime_cutoff_is_inclusive_at_c_threshold(self):
        result = guard.check_capacity(
            c_free=guard.GIB * 20,
            d_free=guard.GIB * 200,
            managed_bytes=0,
            phase="runtime",
        )
        self.assertIn("C:", result)

    def test_runtime_cutoff_is_inclusive_at_d_threshold(self):
        result = guard.check_capacity(
            c_free=guard.GIB * 100,
            d_free=guard.GIB * 80,
            managed_bytes=0,
            phase="runtime",
        )
        self.assertIn("D:", result)

    def test_budget_is_rejected_at_or_above_cap(self):
        result = guard.check_capacity(
            c_free=guard.GIB * 100,
            d_free=guard.GIB * 200,
            managed_bytes=guard.MAX_MANAGED_BYTES,
            phase="start",
        )
        self.assertIn("budget", result.lower())

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_only_d_qa_storage_root_is_accepted(self):
        accepted = Path("D:/QA-Storage/Fable2")
        self.assertEqual(guard.validate_managed_root(accepted), accepted.resolve())
        with self.assertRaises(guard.GuardError):
            guard.validate_managed_root(Path("C:/temp/qa"))
        with self.assertRaises(guard.GuardError):
            guard.validate_managed_root(Path("D:/QA-Storage-Evil/run"))

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_environment_redirects_temp_and_nuget_to_managed_d_root(self):
        root = Path("D:/QA-Storage/Fable2")
        environment = guard.build_environment(root, {"PATH": "sentinel"})
        self.assertTrue(environment["TEMP"].startswith(str(root)))
        self.assertTrue(environment["TMP"].startswith(str(root)))
        self.assertTrue(environment["NUGET_PACKAGES"].startswith(str(root)))
        self.assertEqual(environment["PATH"], "sentinel")

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_real_supervisor_kills_only_its_child_on_timeout(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
                managed = Path(temporary)
                exit_code = guard.run_guarded(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    ROOT,
                    root=managed,
                    timeout_seconds=1,
                    poll_seconds=0.1,
                )
                manifests = list((managed / "fable2-active" / "runs").glob("*/run.json"))
                self.assertEqual(exit_code, 124)
                record = json.loads(manifests[0].read_text(encoding="utf-8"))
                self.assertEqual(record["status"], "timeout")
                self.assertEqual(record["supervisor_pid"], os.getpid())
                self.assertTrue(record["termination_verified"])
                self.assertFalse(guard._pid_is_alive(record["child_pid"]))
            self.assertIsNone(unrelated.poll(), "an unrelated process must remain running")
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=10)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_real_supervisor_timeout_kills_descendants_but_not_unrelated_processes(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
                managed = Path(temporary)
                pid_file = managed / "descendant.pid"
                payload = (
                    "import subprocess,sys,time,pathlib; "
                    "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
                    "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
                )
                exit_code = guard.run_guarded(
                    [sys.executable, "-c", payload, str(pid_file)],
                    ROOT,
                    root=managed,
                    timeout_seconds=2,
                    poll_seconds=0.1,
                )
                record = json.loads(next((managed / "fable2-active" / "runs").glob("*/run.json")).read_text(encoding="utf-8"))
                self.assertEqual(exit_code, 124)
                self.assertTrue(record["termination_verified"])
                self.assertFalse(guard._pid_is_alive(int(pid_file.read_text(encoding="utf-8"))))
            self.assertIsNone(unrelated.poll(), "an unrelated process must remain running")
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=10)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_stale_run_reconciliation_is_dry_run_by_default(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            run_dir = managed / "fable2-active" / "runs" / "20261115T004931Z-33712-00bb0825"
            run_dir.mkdir(parents=True)
            record = {
                "owner": guard.OWNER,
                "run_id": run_dir.name,
                "status": "running",
                "child_pid": 36668,
            }
            manifest = run_dir / "run.json"
            original = json.dumps(record).encode("utf-8")
            manifest.write_bytes(original)

            with mock.patch.object(guard, "_pid_is_alive", return_value=False):
                results = guard.reconcile_stale_runs(managed)

            self.assertEqual(results[0]["action"], "would-mark-interrupted")
            self.assertEqual(manifest.read_bytes(), original)
            self.assertFalse((run_dir / "run.json.pre-reconcile").exists())

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_stale_run_reconciliation_records_unknown_exit_without_claiming_timeout(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            run_dir = managed / "fable2-active" / "runs" / "20261115T004931Z-33712-00bb0825"
            run_dir.mkdir(parents=True)
            record = {
                "owner": guard.OWNER,
                "run_id": run_dir.name,
                "status": "running",
                "supervisor_pid": 33712,
                "child_pid": 36668,
            }
            manifest = run_dir / "run.json"
            original = json.dumps(record).encode("utf-8")
            manifest.write_bytes(original)

            with mock.patch.object(guard, "_pid_is_alive", return_value=False):
                results = guard.reconcile_stale_runs(managed, run_ids=[run_dir.name], apply=True)

            updated = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(results[0]["action"], "marked-interrupted")
            self.assertEqual(updated["status"], "interrupted")
            self.assertEqual(
                updated["reason"],
                "Supervisor and child were absent at reconciliation; exit cause is unknown",
            )
            self.assertNotIn("return_code", updated)
            self.assertNotIn("ended_utc", updated)
            self.assertNotIn("termination_verified", updated)
            self.assertEqual((run_dir / "run.json.pre-reconcile").read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_stale_run_reconciliation_does_not_reclassify_a_live_supervisor(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            run_dir = managed / "fable2-active" / "runs" / "live-run"
            run_dir.mkdir(parents=True)
            manifest = run_dir / "run.json"
            manifest.write_text(json.dumps({
                "owner": guard.OWNER,
                "run_id": run_dir.name,
                "status": "running",
                "supervisor_pid": 33712,
                "child_pid": 36668,
            }), encoding="utf-8")

            with mock.patch.object(guard, "_pid_is_alive", side_effect=lambda pid: pid == 33712):
                results = guard.reconcile_stale_runs(managed, run_ids=[run_dir.name], apply=True)

            self.assertEqual(results[0]["action"], "still-active")
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["status"], "running")

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_stale_run_reconciliation_requires_explicit_ids_for_mutation(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            with self.assertRaises(guard.GuardError):
                guard.reconcile_stale_runs(Path(temporary), apply=True)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_stale_run_reconciliation_leaves_non_object_records_untouched(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            run_dir = managed / "fable2-active" / "runs" / "bad-record"
            run_dir.mkdir(parents=True)
            manifest = run_dir / "run.json"
            original = b"[]"
            manifest.write_bytes(original)

            results = guard.reconcile_stale_runs(managed)

            self.assertEqual(results[0]["action"], "invalid-record")
            self.assertEqual(manifest.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_real_supervisor_caps_trace_file_and_keeps_it(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            trace = managed / "evidence" / "bounded.csv"
            payload = "from pathlib import Path; import sys,time; p=Path(sys.argv[1]); p.parent.mkdir(exist_ok=True); p.write_bytes(b'x'*4096); time.sleep(30)"
            exit_code = guard.run_guarded(
                [sys.executable, "-c", payload, str(trace)],
                ROOT,
                root=managed,
                timeout_seconds=30,
                poll_seconds=0.1,
                trace_file=trace,
                trace_max_bytes=2048,
            )
            record = json.loads(next((managed / "fable2-active" / "runs").glob("*/run.json")).read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 124)
            self.assertEqual(record["status"], "trace-size-limit")
            self.assertTrue(trace.exists(), "trace evidence is never removed by the guard")
            self.assertEqual(trace.stat().st_size, 4096)

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_real_supervisor_stops_capture_when_trace_never_appears(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            trace = managed / "evidence" / "missing.csv"
            exit_code = guard.run_guarded(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                ROOT,
                root=managed,
                timeout_seconds=30,
                poll_seconds=0.1,
                trace_file=trace,
                trace_max_bytes=2048,
                trace_start_timeout_seconds=1,
            )
            record = json.loads(next((managed / "fable2-active" / "runs").glob("*/run.json")).read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 124)
            self.assertEqual(record["status"], "trace-not-created")
            self.assertFalse(trace.exists())

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_real_supervisor_caps_command_log_and_keeps_it(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        original_cap = guard.MAX_LOG_BYTES
        guard.MAX_LOG_BYTES = 128
        try:
            with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
                managed = Path(temporary)
                payload = "import sys,time; sys.stdout.write('x'*4096); sys.stdout.flush(); time.sleep(30)"
                exit_code = guard.run_guarded(
                    [sys.executable, "-c", payload],
                    ROOT,
                    root=managed,
                    timeout_seconds=30,
                    poll_seconds=0.1,
                )
                record_path = next((managed / "fable2-active" / "runs").glob("*/run.json"))
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(exit_code, 124)
                self.assertEqual(record["status"], "log-size-limit")
                self.assertTrue(Path(record["log"]).exists(), "logs are preserved")
                self.assertGreaterEqual(Path(record["log"]).stat().st_size, 128)
        finally:
            guard.MAX_LOG_BYTES = original_cap

    def test_etw_tools_are_rejected_by_generic_runner(self):
        with self.assertRaises(guard.GuardError):
            guard._reject_etw(["wpr.exe", "-start", "GPU"])
        with self.assertRaises(guard.GuardError):
            guard._reject_etw(["logman.exe", "start", "trace"])

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_cleanup_removes_only_old_marked_temp_and_preserves_logs(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            managed = Path(temporary)
            run = managed / "fable2-active" / "runs" / "old-run"
            temp_dir = run / "tmp"
            temp_dir.mkdir(parents=True)
            (temp_dir / "scratch.bin").write_bytes(b"rebuildable")
            (run / "command.log").write_text("retained evidence", encoding="utf-8")
            old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            (run / "run.json").write_text(json.dumps({
                "owner": guard.OWNER,
                "run_id": "old-run",
                "status": "completed",
                "ended_utc": old,
                "temporary_directory": str(temp_dir.resolve()),
                "rebuildable_temp_only": True,
            }), encoding="utf-8")
            dry_run = guard.cleanup_old_temp(managed, older_than_days=7, apply=False)
            self.assertEqual(dry_run[0]["action"], "would-remove")
            self.assertTrue(temp_dir.exists())
            applied = guard.cleanup_old_temp(managed, older_than_days=7, apply=True)
            self.assertEqual(applied[0]["action"], "removed")
            self.assertFalse(temp_dir.exists())
            self.assertTrue((run / "command.log").exists())
            self.assertTrue((run / "run.json").exists())

    @unittest.skipUnless(os.name == "nt", "the managed storage policy requires Windows D:")
    def test_build_cleanup_requires_guard_marker_and_preserves_evidence(self):
        fixture_root = Path("D:/QA-Storage/guard-tests")
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            unmarked = repo / "out" / "build" / "win-amd64-release"
            unmarked.mkdir(parents=True)
            with self.assertRaises(guard.GuardError):
                guard.clean_build_dir(repo, "win-amd64-release", apply=True)

            owned_repo = Path(temporary) / "owned-repo"
            owned_repo.mkdir()
            self.assertEqual(guard.mark_build_dir(owned_repo, "win-amd64-release"), "marked")
            build_dir = owned_repo / "out" / "build" / "win-amd64-release"
            dry_run = guard.clean_build_dir(owned_repo, "win-amd64-release", apply=False)
            self.assertEqual(dry_run["action"], "would-remove")
            self.assertTrue(build_dir.exists())
            (build_dir / "capture.csv").write_text("evidence", encoding="utf-8")
            with self.assertRaises(guard.GuardError):
                guard.clean_build_dir(owned_repo, "win-amd64-release", apply=True)
            (build_dir / "capture.csv").unlink()
            applied = guard.clean_build_dir(owned_repo, "win-amd64-release", apply=True)
            self.assertEqual(applied["action"], "removed")
            self.assertFalse(build_dir.exists())


if __name__ == "__main__":
    unittest.main()
