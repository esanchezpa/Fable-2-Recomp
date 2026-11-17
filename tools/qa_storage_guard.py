"""Fail-closed storage and lifetime guard for Fable II QA/build processes.

The guard manages only D:\\QA-Storage and this checkout's out/ tree. It does
not start ETW, WPR, or xperf. Command output, run records, and evidence are
retained; optional cleanup removes only marked, old per-run temp directories.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid


GIB = 1024**3
MANAGED_ROOT = Path(r"D:\QA-Storage")
MIN_START_C = 30 * GIB
MIN_START_D = 100 * GIB
STOP_C = 20 * GIB
STOP_D = 80 * GIB
MAX_MANAGED_BYTES = 64 * GIB
MAX_TRACE_BYTES = 50 * GIB
MAX_TIMEOUT_SECONDS = 4 * 60 * 60
POLL_SECONDS = 1
MAX_LOG_BYTES = GIB
OWNER = "fable2-qa-storage-guard-v1"


class GuardError(RuntimeError):
    pass


def validate_managed_root(path: Path | str) -> Path:
    """Require a path physically contained under D:\\QA-Storage."""
    candidate = Path(path).resolve(strict=False)
    base = MANAGED_ROOT.resolve(strict=False)
    if os.name != "nt":
        raise GuardError("The storage guard is Windows-only")
    if candidate.drive.lower() != "d:":
        raise GuardError(f"Managed storage must be on D:, got {candidate}")
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise GuardError(f"Managed storage must be under {base}, got {candidate}") from exc
    return candidate


def build_environment(root: Path | str, base: dict[str, str] | None = None,
                      temp_dir: Path | str | None = None) -> dict[str, str]:
    """Return a child environment with temporary/package state on D:."""
    managed = validate_managed_root(root)
    active = managed / "fable2-active"
    temp = Path(temp_dir).resolve(strict=False) if temp_dir else active / "shared-temp"
    validate_managed_root(temp)
    env = dict(os.environ if base is None else base)
    env.update({
        "FABLE2_QA_STORAGE_ROOT": str(managed),
        "TEMP": str(temp),
        "TMP": str(temp),
        "TMPDIR": str(temp),
        "NUGET_PACKAGES": str(active / "cache" / "nuget"),
        "DOTNET_CLI_HOME": str(active / "dotnet-home"),
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "PIP_CACHE_DIR": str(active / "cache" / "pip"),
        "npm_config_cache": str(active / "cache" / "npm"),
    })
    return env


def check_capacity(c_free: int, d_free: int, managed_bytes: int,
                   phase: str = "start") -> str | None:
    """Return a blocking reason; thresholds are inclusive at the stop edge."""
    if phase not in {"start", "runtime"}:
        raise ValueError(f"Unsupported capacity phase: {phase}")
    if phase == "start":
        if c_free < MIN_START_C:
            return f"C: free space {c_free / GIB:.2f} GiB is below the 30 GiB start minimum"
        if d_free < MIN_START_D:
            return f"D: free space {d_free / GIB:.2f} GiB is below the 100 GiB start minimum"
    else:
        if c_free <= STOP_C:
            return f"C: free space reached the 20 GiB runtime stop threshold"
        if d_free <= STOP_D:
            return f"D: free space reached the 80 GiB runtime stop threshold"
    if managed_bytes >= MAX_MANAGED_BYTES:
        return f"Managed storage reached the 64 GiB budget"
    return None


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
        raise GuardError(f"Refusing to measure a reparse point: {path}")
    total = 0
    for current, dirs, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            child = current_path / name
            if child.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(child)):
                raise GuardError(f"Reparse point inside measured storage: {child}")
        for name in files:
            child = current_path / name
            if child.is_symlink():
                raise GuardError(f"Symbolic link inside measured storage: {child}")
            try:
                total += child.stat(follow_symlinks=False).st_size
            except FileNotFoundError:
                # A concurrently deleted file can only lower the estimate; the
                # independent free-space checks remain authoritative.
                continue
    return total


def managed_storage_bytes(root: Path | str, repo_root: Path | str) -> int:
    managed = validate_managed_root(root)
    repo = Path(repo_root).resolve(strict=True)
    candidates = [managed]
    build_outputs = [repo / "out", repo / "thirdparty" / "rexglue-sdk" / "out"]
    for out in build_outputs:
        if out.exists():
            if out.drive.lower() != "d:":
                raise GuardError(f"Build output must be on D:, got {out}")
            candidates.append(out.resolve(strict=True))
    # Avoid double-counting if a future layout nests one managed path in another.
    unique: list[Path] = []
    for candidate in candidates:
        if not any(candidate == parent or parent in candidate.parents for parent in unique):
            unique.append(candidate)
    return sum(_directory_size(path) for path in unique)


def _disk_free(drive: str) -> int:
    return shutil.disk_usage(drive + "\\").free


def _capacity_reason(root: Path, repo_root: Path, phase: str) -> tuple[str | None, dict[str, int]]:
    snapshot = {
        "c_free_bytes": _disk_free("C:"),
        "d_free_bytes": _disk_free("D:"),
        "managed_bytes": managed_storage_bytes(root, repo_root),
    }
    reason = check_capacity(snapshot["c_free_bytes"], snapshot["d_free_bytes"],
                            snapshot["managed_bytes"], phase=phase)
    return reason, snapshot


def _atomic_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _reject_etw(argv: list[str]) -> None:
    if not argv:
        raise GuardError("No command was supplied")
    command_text = " ".join(argv).lower()
    if re.search(r"(?:^|[\\/\s\"'])((?:wpr|logman|xperf)(?:\.exe)?)(?=$|[\s\"'])", command_text):
        raise GuardError("WPR/logman/xperf are blocked by the generic runner; no bounded ETW runner is configured")


def _terminate_owned_tree(process: subprocess.Popen[bytes]) -> tuple[bool, str]:
    """Terminate only the process tree rooted at our still-live child PID."""
    if process.poll() is not None:
        return True, "root process already exited"
    if os.name != "nt":
        process.terminate()
        try:
            process.wait(timeout=10)
            return True, "terminated direct child (non-Windows test path)"
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            return True, "killed direct child (non-Windows test path)"
    result = subprocess.run(
        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        return False, f"taskkill exit {result.returncode}; owned root PID {process.pid} still alive"
    return True, f"taskkill /T exit {result.returncode}; owned root PID {process.pid} exited"


def _command_for_windows(argv: list[str]) -> list[str]:
    executable = Path(argv[0])
    if executable.suffix.lower() not in {".cmd", ".bat"}:
        return argv
    command = "call " + subprocess.list2cmdline(argv)
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]


def run_guarded(argv: list[str], repo_root: Path | str, root: Path | str = MANAGED_ROOT,
                timeout_seconds: int = MAX_TIMEOUT_SECONDS, poll_seconds: float = POLL_SECONDS,
                trace_file: Path | str | None = None,
                trace_max_bytes: int | None = None,
                trace_start_timeout_seconds: int | None = None,
                build_child: bool = False) -> int:
    managed = validate_managed_root(root)
    repository = Path(repo_root).resolve(strict=True)
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise GuardError(f"Timeout must be from 1 to {MAX_TIMEOUT_SECONDS} seconds")
    if poll_seconds <= 0:
        raise GuardError("Polling interval must be positive")
    _reject_etw(argv)

    monitored_trace: Path | None = None
    if trace_file is not None or trace_max_bytes is not None:
        if trace_file is None or trace_max_bytes is None or trace_max_bytes <= 0:
            raise GuardError("A trace output and positive maximum byte count must be supplied together")
        monitored_trace = Path(trace_file).resolve(strict=False)
        if not _is_under(monitored_trace, managed) or monitored_trace.drive.lower() != "d:":
            raise GuardError("Trace output must resolve under the managed D: root")
        if trace_max_bytes > MAX_TRACE_BYTES:
            raise GuardError("Trace size cap cannot exceed the 50 GiB trace budget")
        if monitored_trace.exists():
            raise GuardError(f"Refusing to overwrite existing trace: {monitored_trace}")
    if monitored_trace is not None:
        trace_start_timeout_seconds = (min(120, timeout_seconds)
                                       if trace_start_timeout_seconds is None
                                       else trace_start_timeout_seconds)
        if not 1 <= trace_start_timeout_seconds <= timeout_seconds:
            raise GuardError("Trace startup timeout must be positive and no greater than the run timeout")

    reason, snapshot = _capacity_reason(managed, repository, "start")
    if reason:
        raise GuardError("Preflight blocked: " + reason)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    active = managed / "fable2-active"
    run_dir = active / "runs" / run_id
    temp_dir = run_dir / "tmp"
    log_path = run_dir / "command.log"
    manifest_path = run_dir / "run.json"
    temp_dir.mkdir(parents=True, exist_ok=False)
    if monitored_trace is not None:
        monitored_trace.parent.mkdir(parents=True, exist_ok=True)
    env = build_environment(managed, temp_dir=temp_dir)
    env["FABLE2_QA_RUN_DIR"] = str(run_dir)
    env["FABLE2_QA_TEMP_DIR"] = str(temp_dir)
    if monitored_trace:
        env["REX_FRAME_EVENT_TRACE"] = str(monitored_trace)
    nonce = uuid.uuid4().hex
    if build_child:
        env["FABLE2_STORAGE_GUARD_ACTIVE"] = "1"
        env["FABLE2_STORAGE_GUARD_MANIFEST"] = str(manifest_path)
        env["FABLE2_STORAGE_GUARD_NONCE"] = nonce
        env["FABLE2_STORAGE_GUARD_PID"] = str(os.getpid())

    started = datetime.now(timezone.utc)
    run_record: dict[str, object] = {
        "owner": OWNER,
        "run_id": run_id,
        "status": "running",
        "supervisor_pid": os.getpid(),
        "repository": str(repository),
        "managed_root": str(managed),
        "temporary_directory": str(temp_dir),
        "log": str(log_path),
        "started_utc": started.isoformat(),
        "timeout_seconds": timeout_seconds,
        "poll_seconds": poll_seconds,
        "initial_capacity": snapshot,
        "preserve": ["run.json", "command.log", "evidence", "saves", "configs", "XEX", "CSV", "logs"],
        "rebuildable_temp_only": True,
    }
    if build_child:
        run_record.update({"guard_nonce": nonce, "guard_pid": os.getpid()})
    _atomic_json(manifest_path, run_record)

    child_argv = _command_for_windows(argv)
    process: subprocess.Popen[bytes] | None = None
    status = "failed-to-launch"
    return_code = 125
    reason_text = ""
    started_clock = time.monotonic()
    try:
        with log_path.open("xb") as log:
            process = subprocess.Popen(child_argv, cwd=repository, env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            run_record["child_pid"] = process.pid
            _atomic_json(manifest_path, run_record)
            while process.poll() is None:
                if time.monotonic() - started_clock >= timeout_seconds:
                    status = "timeout"
                    reason_text = f"Command exceeded {timeout_seconds} seconds"
                    break
                if log_path.stat().st_size >= MAX_LOG_BYTES:
                    status = "log-size-limit"
                    reason_text = f"Command log reached {MAX_LOG_BYTES} bytes"
                    break
                if monitored_trace is not None and monitored_trace.exists():
                    if monitored_trace.stat().st_size >= int(trace_max_bytes):
                        status = "trace-size-limit"
                        reason_text = f"Trace reached {trace_max_bytes} bytes"
                        break
                elif (monitored_trace is not None and trace_start_timeout_seconds is not None
                      and time.monotonic() - started_clock >= trace_start_timeout_seconds):
                    status = "trace-not-created"
                    reason_text = f"Trace file was not created within {trace_start_timeout_seconds} seconds"
                    break
                reason, snapshot = _capacity_reason(managed, repository, "runtime")
                if reason:
                    status = "storage-limit"
                    reason_text = reason
                    break
                time.sleep(min(poll_seconds, max(0.05, timeout_seconds - (time.monotonic() - started_clock))))
            if process.poll() is None:
                terminated, termination = _terminate_owned_tree(process)
                run_record["termination_verified"] = terminated
                run_record["termination_detail"] = termination
                if not terminated:
                    status = "termination-unverified"
                    return_code = 125
                else:
                    return_code = 124
            else:
                return_code = int(process.returncode or 0)
                if status == "failed-to-launch":
                    status = "completed" if return_code == 0 else "command-failed"
                reason_text = reason_text or ""
    except (OSError, subprocess.SubprocessError, GuardError) as exc:
        reason_text = str(exc)
        if process is not None and process.poll() is None:
            terminated, termination = _terminate_owned_tree(process)
            run_record["termination_verified"] = terminated
            run_record["termination_detail"] = termination
            if not terminated:
                status = "termination-unverified"

    ended = datetime.now(timezone.utc)
    run_record.update({
        "status": status,
        "return_code": return_code,
        "reason": reason_text,
        "ended_utc": ended.isoformat(),
        "elapsed_seconds": round(time.monotonic() - started_clock, 3),
        "final_capacity": snapshot,
        "command_log_bytes": log_path.stat().st_size if log_path.exists() else 0,
        "trace_file": str(monitored_trace) if monitored_trace else None,
        "trace_max_bytes": trace_max_bytes,
        "trace_start_timeout_seconds": trace_start_timeout_seconds if monitored_trace else None,
    })
    _atomic_json(manifest_path, run_record)
    print(json.dumps({"status": status, "return_code": return_code,
                      "run_id": run_id, "run_record": str(manifest_path),
                      "log": str(log_path), "reason": reason_text}, indent=2))
    return return_code


def reconcile_stale_runs(root: Path | str = MANAGED_ROOT,
                         run_ids: list[str] | None = None,
                         apply: bool = False) -> list[dict[str, object]]:
    """Report or conservatively reclassify runs whose supervisor and child are absent.

    An external host can terminate this supervisor before it writes a final status.
    Reconciliation records only process absence at inspection; it never invents an
    exit code, end time, successful termination, or the cause of interruption.
    """
    managed = validate_managed_root(root)
    if apply and not run_ids:
        raise GuardError("Applying stale-run reconciliation requires at least one explicit run ID")
    runs = managed / "fable2-active" / "runs"
    if runs.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(runs)):
        raise GuardError(f"Refusing to inspect a reparse point: {runs}")
    if not runs.exists():
        return []
    requested = set(run_ids) if run_ids is not None else None
    if requested is not None:
        for run_id in requested:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
                raise GuardError(f"Invalid run ID: {run_id}")
    results: list[dict[str, object]] = []
    for run_dir in sorted(runs.iterdir()):
        if (not run_dir.is_dir() or run_dir.is_symlink()
                or (hasattr(os.path, "isjunction") and os.path.isjunction(run_dir))):
            continue
        if requested is not None and run_dir.name not in requested:
            continue
        manifest = run_dir / "run.json"
        if (manifest.is_symlink()
                or (hasattr(os.path, "isjunction") and os.path.isjunction(manifest))):
            results.append({"run_id": run_dir.name, "action": "manual-review-reparse-point"})
            continue
        if not manifest.is_file():
            continue
        try:
            original_bytes = manifest.read_bytes()
            record = json.loads(original_bytes.decode("utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            results.append({"run_id": run_dir.name, "action": "invalid-record", "reason": str(exc)})
            continue
        if not isinstance(record, dict):
            results.append({"run_id": run_dir.name, "action": "invalid-record",
                            "reason": "run record must contain a JSON object"})
            continue
        if record.get("owner") != OWNER or record.get("status") != "running":
            continue

        supervisor_pid = record.get("supervisor_pid", record.get("guard_pid"))
        if not isinstance(supervisor_pid, int) or supervisor_pid <= 0:
            # Older records encode the supervisor PID in the guard-generated run ID.
            match = re.fullmatch(r"\d{8}T\d{6}Z-(\d+)-[0-9a-fA-F]{8}",
                                 str(record.get("run_id", run_dir.name)))
            supervisor_pid = int(match.group(1)) if match else 0
        child_pid = record.get("child_pid")
        if not isinstance(child_pid, int) or child_pid <= 0 or supervisor_pid <= 0:
            results.append({"run_id": run_dir.name, "action": "manual-review-missing-pids"})
            continue

        supervisor_alive = _pid_is_alive(supervisor_pid)
        child_alive = _pid_is_alive(child_pid)
        if supervisor_alive or child_alive:
            results.append({"run_id": run_dir.name, "action": "still-active",
                            "supervisor_alive": supervisor_alive, "child_alive": child_alive})
            continue

        result: dict[str, object] = {
            "run_id": run_dir.name,
            "action": "would-mark-interrupted",
        }
        if apply:
            backup = manifest.with_name("run.json.pre-reconcile")
            if backup.exists():
                if backup.read_bytes() != original_bytes:
                    results.append({"run_id": run_dir.name,
                                    "action": "preserved-conflicting-backup"})
                    continue
            else:
                try:
                    with backup.open("xb") as stream:
                        stream.write(original_bytes)
                except FileExistsError:
                    # Another reconciler won the race; only proceed if it saved
                    # this exact still-running record as the original.
                    if backup.read_bytes() != original_bytes:
                        results.append({"run_id": run_dir.name,
                                        "action": "preserved-conflicting-backup"})
                        continue
            reconciled = dict(record)
            reconciled.update({
                "status": "interrupted",
                "reason": "Supervisor and child were absent at reconciliation; exit cause is unknown",
                "reconciliation": {
                    "observed_utc": datetime.now(timezone.utc).isoformat(),
                    "observer_pid": os.getpid(),
                    "supervisor_pid": supervisor_pid,
                    "child_pid": child_pid,
                    "supervisor_alive": False,
                    "child_alive": False,
                    "exit_code": None,
                    "termination_cause": "unknown",
                },
            })
            _atomic_json(manifest, reconciled)
            result.update({"action": "marked-interrupted", "backup": str(backup)})
        results.append(result)
    if requested is not None:
        found = {str(item.get("run_id")) for item in results}
        for run_id in sorted(requested - found):
            results.append({"run_id": run_id, "action": "not-found-or-not-running"})
    return results


def verify_build_child(manifest: Path | str, nonce: str, guard_pid: int,
                       repository: Path | str) -> bool:
    try:
        manifest_path = Path(manifest).resolve(strict=True)
        managed = validate_managed_root(manifest_path)
        del managed
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_repository = Path(repository).resolve(strict=True)
        return (
            data.get("owner") == OWNER
            and data.get("status") == "running"
            and data.get("guard_nonce") == nonce
            and data.get("guard_pid") == guard_pid
            and Path(data.get("repository", "")).resolve(strict=False) == expected_repository
            and _pid_is_alive(guard_pid)
        )
    except (OSError, ValueError, GuardError, TypeError):
        return False


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cleanup_old_temp(root: Path | str = MANAGED_ROOT, older_than_days: int = 7,
                     apply: bool = False) -> list[dict[str, object]]:
    """List or remove only marked temp subdirectories of completed old runs."""
    managed = validate_managed_root(root)
    if older_than_days < 1 or older_than_days > 365:
        raise GuardError("Cleanup age must be 1..365 days")
    runs = managed / "fable2-active" / "runs"
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    results: list[dict[str, object]] = []
    if not runs.exists():
        return results
    for run_dir in runs.iterdir():
        manifest = run_dir / "run.json"
        temp_dir = run_dir / "tmp"
        if not run_dir.is_dir() or run_dir.is_symlink() or not manifest.is_file():
            continue
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
            ended = datetime.fromisoformat(str(record["ended_utc"]))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if (record.get("owner") != OWNER or record.get("status") not in
                {"completed", "command-failed", "timeout", "storage-limit", "log-size-limit",
                 "trace-size-limit", "trace-not-created"}):
            continue
        if ended.tzinfo is None or ended > cutoff or not temp_dir.exists():
            continue
        if temp_dir.is_symlink() or not _is_under(temp_dir, runs):
            continue
        if record.get("temporary_directory") != str(temp_dir.resolve(strict=False)):
            continue
        if record.get("rebuildable_temp_only") is not True:
            continue
        if _pid_is_alive(int(record.get("child_pid", 0))):
            continue
        size = _directory_size(temp_dir)
        item = {"run_id": record.get("run_id"), "temp_directory": str(temp_dir),
                "bytes": size, "action": "would-remove"}
        if apply:
            shutil.rmtree(temp_dir)
            item["action"] = "removed"
        results.append(item)
    return results


def _build_dir(repo_root: Path | str, config: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", config):
        raise GuardError(f"Invalid build configuration name: {config}")
    repo = Path(repo_root).resolve(strict=True)
    if repo.drive.lower() != "d:":
        raise GuardError("Build repository must be on D:")
    base = (repo / "out" / "build").resolve(strict=False)
    target = (base / config).resolve(strict=False)
    if not _is_under(target, base) or target == base:
        raise GuardError("Build directory escaped the repository out/build root")
    return repo, target


def mark_build_dir(repo_root: Path | str, config: str) -> str:
    """Mark only a new, empty build directory as owned/reconstructible."""
    repo, build_dir = _build_dir(repo_root, config)
    marker = build_dir / ".fable2-qa-build-owned.json"
    if build_dir.exists():
        if marker.is_file():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise GuardError(f"Invalid build ownership marker: {marker}")
            if data.get("owner") == OWNER and data.get("repository") == str(repo) and data.get("config") == config:
                return "already-marked"
        return "existing-unmarked"
    build_dir.mkdir(parents=True, exist_ok=False)
    _atomic_json(marker, {"owner": OWNER, "repository": str(repo), "config": config,
                          "created_utc": datetime.now(timezone.utc).isoformat(),
                          "rebuildable_build_output": True})
    return "marked"


def clean_build_dir(repo_root: Path | str, config: str, apply: bool = False) -> dict[str, object]:
    """Clean a build tree only when guard-owned and free of evidence/user data."""
    repo, build_dir = _build_dir(repo_root, config)
    if not build_dir.exists():
        return {"path": str(build_dir), "action": "absent"}
    if build_dir.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(build_dir)):
        raise GuardError("Refusing to clean a reparse-point build directory")
    marker = build_dir / ".fable2-qa-build-owned.json"
    if not marker.is_file():
        raise GuardError(f"Refusing to clean an unmarked build tree: {build_dir}")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuardError(f"Invalid build ownership marker: {marker}") from exc
    if (data.get("owner") != OWNER or data.get("repository") != str(repo)
            or data.get("config") != config or data.get("rebuildable_build_output") is not True):
        raise GuardError("Build ownership marker does not match this checkout/configuration")
    cache = build_dir / "CMakeCache.txt"
    if cache.exists():
        cache_text = cache.read_text(encoding="utf-8", errors="replace")
        home = re.search(r"^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)$", cache_text, re.MULTILINE)
        if not home or Path(home.group(1)).resolve(strict=False) != repo:
            raise GuardError("CMakeCache source directory does not match this repository")
    preserved_extensions = {".csv", ".etl", ".xex", ".sav", ".log"}
    preserved_names = {"evidence", "saves", "logs"}
    for current, directories, files in os.walk(build_dir, followlinks=False):
        current_path = Path(current)
        for name in directories:
            child = current_path / name
            if name.lower() in preserved_names:
                raise GuardError(f"Refusing to remove preserved-data directory: {child}")
            if child.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(child)):
                raise GuardError(f"Refusing to remove reparse point: {child}")
        for name in files:
            if Path(name).suffix.lower() in preserved_extensions:
                raise GuardError(f"Refusing to remove preserved artifact: {current_path / name}")
    size = _directory_size(build_dir)
    result = {"path": str(build_dir), "bytes": size,
              "action": "would-remove" if not apply else "removed"}
    if apply:
        shutil.rmtree(build_dir)
    return result


def gameplay_command(game_root: Path | str, backend: str) -> list[str]:
    """Build a direct game command, restricted to a copied QA tree on D:."""
    if backend not in {"d3d12", "vulkan", "prebuilt"}:
        raise GuardError(f"Unsupported gameplay backend: {backend}")
    managed = validate_managed_root(MANAGED_ROOT)
    game = Path(game_root).resolve(strict=True)
    if game.drive.lower() != "d:" or not _is_under(game, managed):
        raise GuardError("Gameplay must launch from a copied game tree under D:\\QA-Storage")
    executable = game / "fable_2.exe"
    if not executable.is_file():
        raise GuardError(f"QA game executable not found: {executable}")
    plugin = "xenos-vulkan" if backend == "vulkan" else "xenos"
    return [str(executable), f"--gpu_plugin={plugin}"]


def launch_gameplay(game_root: Path | str, backend: str = "d3d12",
                    timeout_seconds: int = MAX_TIMEOUT_SECONDS,
                    trace_max_bytes: int = 64 * 1024 * 1024) -> int:
    managed = validate_managed_root(MANAGED_ROOT)
    game = Path(game_root).resolve(strict=True)
    command = gameplay_command(game, backend)
    evidence = managed / "fable2-active" / "evidence"
    trace_name = (datetime.now(timezone.utc).strftime("frame-events-%Y%m%dT%H%M%SZ-")
                  + f"{os.getpid()}-{uuid.uuid4().hex[:8]}.csv")
    return run_guarded(command, game, root=managed, timeout_seconds=timeout_seconds,
                       trace_file=evidence / trace_name, trace_max_bytes=trace_max_bytes,
                       trace_start_timeout_seconds=min(120, timeout_seconds))


def _build_command(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve(strict=True)
    build_cmd = repo / "build.cmd"
    if not build_cmd.is_file():
        raise GuardError(f"Build entrypoint not found: {build_cmd}")
    command = [str(build_cmd), *args.build_args]
    return run_guarded(command, repo, root=MANAGED_ROOT,
                       timeout_seconds=args.timeout_seconds, build_child=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    build = subparsers.add_parser("build", help="run build.cmd under the storage supervisor")
    build.add_argument("--repo-root", required=True)
    build.add_argument("--timeout-seconds", type=int, default=MAX_TIMEOUT_SECONDS)
    build.add_argument("build_args", nargs=argparse.REMAINDER)
    run = subparsers.add_parser("run", help="run one QA process under the storage supervisor")
    run.add_argument("--repo-root", required=True)
    run.add_argument("--timeout-seconds", type=int, default=MAX_TIMEOUT_SECONDS)
    run.add_argument("--trace-file")
    run.add_argument("--trace-max-bytes", type=int)
    run.add_argument("command", nargs=argparse.REMAINDER)
    gameplay = subparsers.add_parser("gameplay", help="launch only the copied QA game under the supervisor")
    gameplay.add_argument("--repo-root", required=True)
    gameplay.add_argument("--game-root", required=True)
    gameplay.add_argument("--backend", choices=("d3d12", "vulkan", "prebuilt"), default="d3d12")
    gameplay.add_argument("--timeout-seconds", type=int, default=MAX_TIMEOUT_SECONDS)
    gameplay.add_argument("--trace-max-bytes", type=int, default=64 * 1024 * 1024)
    preflight = subparsers.add_parser("preflight", help="report current storage headroom without starting work")
    preflight.add_argument("--repo-root", required=True)
    verify = subparsers.add_parser("verify-build-child", help=argparse.SUPPRESS)
    verify.add_argument("--repo-root", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--nonce", required=True)
    verify.add_argument("--guard-pid", required=True, type=int)
    cleanup = subparsers.add_parser("cleanup-temp", help="prune old marked temp dirs only")
    cleanup.add_argument("--older-than-days", type=int, default=7)
    cleanup.add_argument("--apply", action="store_true", help="perform the listed temp-only removals")
    reconcile = subparsers.add_parser(
        "reconcile-stale", help="report or explicitly reconcile stale guarded run records"
    )
    reconcile.add_argument(
        "--run-id", action="append",
        help="limit reconciliation to this exact run ID; repeatable",
    )
    reconcile.add_argument(
        "--apply", action="store_true",
        help="mark selected inactive runs interrupted, preserving original run.json",
    )
    mark = subparsers.add_parser("mark-build-dir", help=argparse.SUPPRESS)
    mark.add_argument("--repo-root", required=True)
    mark.add_argument("--config", required=True)
    clean_build = subparsers.add_parser("clean-build", help=argparse.SUPPRESS)
    clean_build.add_argument("--repo-root", required=True)
    clean_build.add_argument("--config", required=True)
    clean_build.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.mode == "build":
            build_args = args.build_args
            if build_args and build_args[0] == "--":
                build_args = build_args[1:]
            args.build_args = build_args
            return _build_command(args)
        if args.mode == "run":
            command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            return run_guarded(command, args.repo_root, root=MANAGED_ROOT,
                               timeout_seconds=args.timeout_seconds,
                               trace_file=args.trace_file, trace_max_bytes=args.trace_max_bytes)
        if args.mode == "gameplay":
            repository = Path(args.repo_root).resolve(strict=True)
            if repository.drive.lower() != "d:":
                raise GuardError("QA repository must be on D:")
            return launch_gameplay(args.game_root, backend=args.backend,
                                   timeout_seconds=args.timeout_seconds,
                                   trace_max_bytes=args.trace_max_bytes)
        if args.mode == "preflight":
            root = validate_managed_root(MANAGED_ROOT)
            reason, snapshot = _capacity_reason(root, Path(args.repo_root).resolve(strict=True), "start")
            print(json.dumps({"allowed": reason is None, "reason": reason,
                              "managed_root": str(root), "capacity": snapshot,
                              "thresholds": {"min_start_c": MIN_START_C,
                                             "min_start_d": MIN_START_D,
                                             "max_managed": MAX_MANAGED_BYTES}}, indent=2))
            return 0 if reason is None else 125
        if args.mode == "verify-build-child":
            return 0 if verify_build_child(args.manifest, args.nonce, args.guard_pid,
                                           args.repo_root) else 125
        if args.mode == "cleanup-temp":
            print(json.dumps(cleanup_old_temp(root=MANAGED_ROOT, older_than_days=args.older_than_days,
                                             apply=args.apply), indent=2))
            return 0
        if args.mode == "reconcile-stale":
            print(json.dumps(reconcile_stale_runs(root=MANAGED_ROOT, run_ids=args.run_id,
                                                  apply=args.apply), indent=2))
            return 0
        if args.mode == "mark-build-dir":
            result = mark_build_dir(args.repo_root, args.config)
            print(json.dumps({"result": result, "config": args.config}))
            return 0
        if args.mode == "clean-build":
            print(json.dumps(clean_build_dir(args.repo_root, args.config, apply=args.apply), indent=2))
            return 0
    except GuardError as exc:
        print(f"QA storage guard blocked operation: {exc}", file=sys.stderr)
        return 125
    return 125


if __name__ == "__main__":
    raise SystemExit(main())
