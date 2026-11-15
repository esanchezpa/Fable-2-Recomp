# Offline input-block comparison — 2026-11-15

## Scope

Compare the guarded title-screen run `20261115T002651Z-36344-9279ffff` with the successful gameplay navigation recorded for `20261114T155121Z-16332-dea4fc71`. This is artifact-only analysis: no game launch, visual re-test, or mutation of the QA clone, `console/state.txt`, or saves.

## Observations

- Failed run evidence is under `D:\QA-Storage\fable2-active\evidence\f5diag-console-ack-20261115T002402Z`; its `inputs.jsonl` records one input, `pad a 10`, at `2026-11-15T00:27:52.6179725Z`. The result records title/attract observations, no gameplay, no `out.txt` delta, and no observed pump error or timeout. `in.txt` was absent after the run, but the successful `pad` handler does not emit an `out.txt` acknowledgement; absence is not proof of dispatch or receipt.
- That run ended at its 300-second watchdog with code 124 and verified process termination. Save witness: 40 expected, 40 actual, zero differences. Manifest/config/SDK config/EXE hashes were unchanged during the run. `console/state.txt` changed and was retained as a post-run snapshot, not restored.
- Successful navigation evidence is described in `qa/execution-report.md` section 55 and observer `D:\QA-Storage\fable2-active\evidence\title-transition-retry-20261114\window-observation2.jsonl`: staged `pad a 10` -> `pad down 12` -> `pad a 12` reached the save and Old Bowerstone gameplay. The observer recorded 1,110 samples; 1,106 had the game window visible and foreground in the interactive session.
- Both runs targeted `D:\QA-Storage\fable2-active\gameplay-pair-20261113`. The successful run's game log records the config load and GOTY Spain profile. The failed run's log does too. The currently preserved config maps E/Shift to A and S to StickDown. Available post-run hashes do not establish complete byte-for-byte identity of every build/config input across the two runs.

## Interpretation and next validation

The concrete recorded difference is the successful staged navigation versus the failed run's single archived pad command. This supports only a testable hypothesis: a single A during a title/attract transition may not be enough, or may coincide with a non-actionable screen phase. It does not establish a cause in the input channel, focus, pump, timing, or build. The failed attempt also had later host-key observations, so the runs are not a controlled A/B pair.

No new static test was added. Existing pump contract tests cover source-level ingestion and acknowledgement paths; they cannot prove SDL/host input reached the game's title handler. A source-only test would not resolve this runtime uncertainty.

Next visual run, when authorized and available: wait for a stable title prompt, send one A through the previously successful pad channel, and confirm the menu before sending down/A. Record each input timestamp and screen. If the first A does not open the menu, stop before `f5diag` and preserve the observation rather than inferring a pump failure. Do not interpret the frame-event trace as unique FPS.
