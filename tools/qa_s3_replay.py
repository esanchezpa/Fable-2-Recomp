"""Build and timestamp a short-step, observable S3 gameplay replay plan."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


MIN_PASS_SECONDS = 180
MAX_ACTION_SECONDS = 2.0
_PATTERN = (
    ("sprint_forward", ("shift", "w"), 1.0),
    ("reorient_left_back", ("a", "s"), 2.0),
    ("sprint_forward", ("shift", "w"), 1.0),
    ("reorient_right_back", ("d", "s"), 2.0),
    ("camera_sweep", ("mouse_delta", 500, 0), 0.1),
    ("camera_sweep", ("mouse_delta", 500, 0), 0.1),
    ("camera_sweep", ("mouse_delta", 500, 0), 0.1),
    ("camera_sweep", ("mouse_delta", 500, 0), 0.1),
)
_MARKER_OWNER = "qa-s3-replay-v1"
MAX_TRACE_BYTES = 32 * 1024 * 1024
MAX_TRACE_ROWS = 250_000


def build_replay_plan(duration_seconds: float = MIN_PASS_SECONDS) -> dict[str, object]:
    """Return the same bounded input cycle for every paired ON/OFF pass.

    Every movement or camera action is an observation boundary: the operator
    must inspect the fresh game frame before and after it and redirect instead
    of repeating the cycle if an obstacle or stalled movement is visible.
    """
    if duration_seconds < MIN_PASS_SECONDS:
        raise ValueError(f"S3 passes must be at least {MIN_PASS_SECONDS} seconds")
    if not duration_seconds < float("inf"):
        raise ValueError("duration_seconds must be finite")

    actions: list[dict[str, object]] = []
    elapsed = 0.0
    index = 0
    while elapsed < duration_seconds:
        kind, controls, planned_duration = _PATTERN[index % len(_PATTERN)]
        action_duration = min(planned_duration, duration_seconds - elapsed)
        actions.append({
            "index": len(actions) + 1,
            "kind": kind,
            "controls": list(controls),
            "duration_seconds": action_duration,
            "offset_seconds": elapsed,
            "observe_before": True,
            "observe_after": True,
        })
        elapsed += action_duration
        index += 1

    return {
        "schema": "fable2-s3-replay-v1",
        "duration_seconds": duration_seconds,
        "max_action_seconds": MAX_ACTION_SECONDS,
        "actions": actions,
        "safety": [
            "Use only an isolated QA clone with a verified save baseline.",
            "Inspect a fresh frame before and after each action.",
            "If motion stalls or an obstacle is near, stop the cycle and choose a clear direction.",
            "Do not count idle, menu, load, or blocked movement toward the 180-second pass.",
        ],
    }


def qpc_now() -> tuple[int, int]:
    """Read the Windows QPC counter and frequency without changing ETW sessions."""
    if os.name != "nt":
        raise OSError("QPC markers require Windows")
    import ctypes

    counter = ctypes.c_longlong()
    frequency = ctypes.c_longlong()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.QueryPerformanceCounter(ctypes.byref(counter)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel32.QueryPerformanceFrequency(ctypes.byref(frequency)):
        raise ctypes.WinError(ctypes.get_last_error())
    return counter.value, frequency.value


def process_cpu_time_100ns(pid: int, expected_exe: Path | str) -> int:
    """Read cumulative CPU time only after verifying the owned QA executable path."""
    if os.name != "nt":
        raise OSError("process CPU sampling requires Windows")
    import ctypes
    from ctypes import wintypes

    if pid <= 0:
        raise ValueError("pid must be positive")
    expected = str(Path(expected_exe).resolve(strict=True)).casefold()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME))
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        image = ctypes.create_unicode_buffer(32768)
        image_size = wintypes.DWORD(len(image))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(image_size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if image.value.casefold() != expected:
            raise ValueError(f"PID {pid} is not the expected isolated QA executable")

        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                        ctypes.byref(kernel), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        to_int = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
        return to_int(kernel) + to_int(user)
    finally:
        kernel32.CloseHandle(handle)


def append_qpc_marker(path: Path | str, name: str, *, qpc: int, frequency: int,
                      process_cpu_100ns: int | None = None) -> None:
    """Append one marker, refusing to append to or replace unrelated evidence."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
        raise ValueError("marker name must be lowercase snake_case")
    if qpc < 0 or frequency <= 0:
        raise ValueError("QPC must be non-negative and frequency must be positive")

    marker_path = Path(path)
    record = {
        "owner": _MARKER_OWNER,
        "name": name,
        "qpc": qpc,
        "frequency": frequency,
        "utc": datetime.now(timezone.utc).isoformat(),
    }
    if process_cpu_100ns is not None:
        if process_cpu_100ns < 0:
            raise ValueError("process CPU time must be non-negative")
        record["process_cpu_100ns"] = process_cpu_100ns
    if marker_path.exists():
        try:
            with marker_path.open("r", encoding="utf-8") as stream:
                first_line = stream.readline()
            first_record = json.loads(first_line)
        except (OSError, json.JSONDecodeError) as exc:
            raise FileExistsError(f"Refusing to append to non-owned evidence: {marker_path}") from exc
        if first_record.get("owner") != _MARKER_OWNER:
            raise FileExistsError(f"Refusing to append to non-owned evidence: {marker_path}")
        mode = "a"
    else:
        mode = "x"
    with marker_path.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def summarize_trace(path: Path | str, start_qpc: int, end_qpc: int) -> dict[str, object]:
    """Summarize mailbox event flow in a QPC window without claiming displayed FPS."""
    if start_qpc < 0 or end_qpc <= start_qpc:
        raise ValueError("trace window must have an increasing, non-negative QPC range")
    trace_path = Path(path)
    try:
        trace_size = trace_path.stat().st_size
    except OSError as exc:
        raise ValueError(f"cannot stat frame-event trace: {exc}") from exc
    if trace_size > MAX_TRACE_BYTES:
        raise ValueError(f"frame-event trace exceeds byte limit ({MAX_TRACE_BYTES})")

    event_counts: dict[str, int] = {}
    state_produced, state_acquired, state_present = 1, 2, 4
    relevant_events = {
        "guest_output_produced": state_produced,
        "guest_output_acquired": state_acquired,
        "dxgi_present_attempt": state_present,
    }
    # One bitmask per nonzero output ID. File and row caps bound this map.
    output_states: dict[str, int] = {}
    last_sequence: dict[str, int] = {}
    sequence_gap_count: dict[str, int] = {}
    sequence_missing_rows: dict[str, int] = {}
    previous_ticks: dict[str, int] = {}
    interval_stats: dict[str, dict[str, int]] = {}
    reuse_events = {event: 0 for event in relevant_events}
    consecutive_reuse_events = dict(reuse_events)
    last_output_id = {event: "" for event in relevant_events}
    rows_in_window = 0
    rows_read = 0
    present_nonzero_results = 0
    with trace_path.open("r", encoding="utf-8-sig", newline="") as stream:
        first_line = stream.readline().strip()
        match = re.fullmatch(r"# clock=qpc,frequency=(\d+)", first_line)
        if not match:
            raise ValueError("trace is missing its QPC clock/frequency header")
        frequency = int(match.group(1))
        if frequency <= 0:
            raise ValueError("trace QPC frequency must be positive")
        reader = csv.DictReader(stream)
        required = {"event", "event_sequence", "clock_ticks", "guest_output_id", "result"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("trace header does not contain required event/QPC fields")
        for row in reader:
            rows_read += 1
            if rows_read > MAX_TRACE_ROWS:
                raise ValueError(f"frame-event trace exceeds row limit ({MAX_TRACE_ROWS})")
            try:
                event = row["event"]
                sequence = int(row["event_sequence"])
                ticks = int(row["clock_ticks"])
                output_id = row["guest_output_id"]
                result = int(row["result"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid frame-event row {rows_read + 2}") from exc
            if (
                not event
                or sequence <= 0
                or ticks < 0
                or not isinstance(output_id, str)
                or len(output_id) > 20
                or not output_id.isdecimal()
            ):
                raise ValueError(f"invalid frame-event row {rows_read + 2}")
            if not start_qpc <= ticks <= end_qpc:
                continue

            rows_in_window += 1
            event_counts[event] = event_counts.get(event, 0) + 1
            previous_sequence = last_sequence.get(event)
            if previous_sequence is not None:
                if sequence > previous_sequence + 1:
                    sequence_gap_count[event] = sequence_gap_count.get(event, 0) + 1
                    sequence_missing_rows[event] = (
                        sequence_missing_rows.get(event, 0) + sequence - previous_sequence - 1
                    )
                elif sequence <= previous_sequence:
                    raise ValueError(f"non-increasing event sequence for {event}")
            last_sequence[event] = sequence

            previous = previous_ticks.get(event)
            if previous is not None:
                delta_ticks = ticks - previous
                if delta_ticks <= 0:
                    raise ValueError(f"non-increasing QPC timestamp for {event}")
                stats = interval_stats.setdefault(
                    event, {"samples": 0, "min_ticks": delta_ticks,
                            "max_ticks": delta_ticks, "sum_ticks": 0}
                )
                stats["samples"] += 1
                stats["min_ticks"] = min(stats["min_ticks"], delta_ticks)
                stats["max_ticks"] = max(stats["max_ticks"], delta_ticks)
                stats["sum_ticks"] += delta_ticks
            previous_ticks[event] = ticks

            state_flag = relevant_events.get(event)
            if event == "dxgi_present_attempt" and result != 0:
                present_nonzero_results += 1
            if state_flag is None or output_id == "0":
                continue
            state = output_states.get(output_id, 0)
            output_states[output_id] = state | state_flag
            if state & state_flag:
                reuse_events[event] += 1
            if last_output_id[event] == output_id:
                consecutive_reuse_events[event] += 1
            last_output_id[event] = output_id

    produced_ids = sum(bool(state & state_produced) for state in output_states.values())
    acquired_ids = sum(bool(state & state_acquired) for state in output_states.values())
    presented_ids = sum(bool(state & state_present) for state in output_states.values())
    intervals_seconds = {
        event: {
            "samples": stats["samples"],
            "min": round(stats["min_ticks"] / frequency, 9),
            "max": round(stats["max_ticks"] / frequency, 9),
            "mean": round(stats["sum_ticks"] / stats["samples"] / frequency, 9),
        }
        for event, stats in sorted(interval_stats.items())
    }
    return {
        "trace": str(path),
        "clock": "qpc",
        "frequency": frequency,
        "start_qpc": start_qpc,
        "end_qpc": end_qpc,
        "duration_seconds": (end_qpc - start_qpc) / frequency,
        "trace_bytes": trace_size,
        "rows_read": rows_read,
        "event_rows": rows_in_window,
        "event_counts": dict(sorted(event_counts.items())),
        "output_production_events": event_counts.get("guest_output_produced", 0),
        "output_acquisition_events": event_counts.get("guest_output_acquired", 0),
        "present_attempts": event_counts.get("dxgi_present_attempt", 0),
        "distinct_output_ids_produced": produced_ids,
        "distinct_output_ids_acquired": acquired_ids,
        "distinct_output_ids_in_present_attempts": presented_ids,
        "unique_nonzero_guest_output_ids_produced": produced_ids,
        "production_id_reuse_events": reuse_events["guest_output_produced"],
        "acquisition_reuse_events": reuse_events["guest_output_acquired"],
        "present_reuse_events": reuse_events["dxgi_present_attempt"],
        "consecutive_production_id_reuse_events": consecutive_reuse_events["guest_output_produced"],
        "consecutive_acquisition_reuse_events": consecutive_reuse_events["guest_output_acquired"],
        "consecutive_present_reuse_events": consecutive_reuse_events["dxgi_present_attempt"],
        "produced_ids_not_acquired_in_window": sum(
            bool(state & state_produced) and not bool(state & state_acquired)
            for state in output_states.values()
        ),
        "acquired_ids_not_presented_in_window": sum(
            bool(state & state_acquired) and not bool(state & state_present)
            for state in output_states.values()
        ),
        "acquired_ids_without_production_in_window": sum(
            bool(state & state_acquired) and not bool(state & state_produced)
            for state in output_states.values()
        ),
        "present_ids_without_acquisition_in_window": sum(
            bool(state & state_present) and not bool(state & state_acquired)
            for state in output_states.values()
        ),
        "present_attempts_with_nonzero_result": present_nonzero_results,
        "sequence_gap_count_by_event": dict(sorted(sequence_gap_count.items())),
        "sequence_missing_rows_by_event": dict(sorted(sequence_missing_rows.items())),
        "intervals_seconds": intervals_seconds,
        "claims_unique_guest_frames": False,
        "claims_scanout": False,
        "interpretation_limit": (
            "IDs correlate output-production events through mailbox acquisition and host "
            "Present attempts only. Unobserved IDs and sequence gaps are window-local; "
            "they do not prove mailbox drops or ETW/display loss. No content uniqueness, "
            "display completion, scanout cadence, or guest FPS is inferred."
        ),
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan", help="print a deterministic, bounded S3 action cycle")
    plan_parser.add_argument("--duration-seconds", type=float, default=MIN_PASS_SECONDS)
    marker_parser = subparsers.add_parser("mark", help="append a scene/pass boundary with QPC")
    marker_parser.add_argument("--file", required=True, type=Path)
    marker_parser.add_argument("--name", required=True)
    marker_parser.add_argument("--pid", type=int)
    marker_parser.add_argument("--expected-exe", type=Path)
    trace_parser = subparsers.add_parser("summarize-trace", help="count events between QPC markers")
    trace_parser.add_argument("--file", required=True, type=Path)
    trace_parser.add_argument("--start-qpc", required=True, type=int)
    trace_parser.add_argument("--end-qpc", required=True, type=int)
    args = parser.parse_args(argv)

    if args.command == "plan":
        print(json.dumps(build_replay_plan(args.duration_seconds), indent=2))
    elif args.command == "mark":
        counter, frequency = qpc_now()
        if (args.pid is None) != (args.expected_exe is None):
            parser.error("--pid and --expected-exe must be supplied together")
        cpu_time = (process_cpu_time_100ns(args.pid, args.expected_exe)
                    if args.pid is not None else None)
        append_qpc_marker(args.file, args.name, qpc=counter, frequency=frequency,
                          process_cpu_100ns=cpu_time)
        print(json.dumps({"file": str(args.file), "name": args.name, "qpc": counter,
                          "frequency": frequency}, separators=(",", ":")))
    else:
        print(json.dumps(summarize_trace(args.file, args.start_qpc, args.end_qpc), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
