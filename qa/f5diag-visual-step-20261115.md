# Bounded visual input check — 2026-11-15

## Outcome

The run did not reach the main menu or gameplay. One `pad a 10` was sent from a visually confirmed title prompt. The next captured frame showed the title's attract scenery and `Pulsa E para empezar`, not the main menu. No `pad down`, further confirmation, or `f5diag` command was sent. The attribution is inconclusive: the frame change does not prove that the pad input was consumed or caused it.

## Preflight and controlled changes

- `game-player` was available. Before launch, it listed no Fable window and `look` confirmed that the prior selected window had closed. Process checks found no game, CDB, or active guarded run.
- `qa_storage_guard.py preflight` allowed the QA run. C: and D: free space exceeded the guard's start thresholds and managed storage was below its cap. The run used only `D:\QA-Storage\fable2-active\gameplay-pair-20261113`; RenderDoc was removed from the child process PATH only.
- The QA runtime scripts did not contain `f5diag`. Exact pre-run copies and hashes of `F5.lua`, `console_cmds.lua`, `console_pump.lua`, `console/state.txt`, `console/out.txt`, the EXE, configs and `default.xex` are under `D:\QA-Storage\fable2-active\evidence\f5diag-visual-step-20261115T004909Z\pre-run`. The checkout's `src/lua/F5.lua` and `src/lua/console_cmds.lua` were temporarily staged to the QA clone only, with their exact hashes recorded in `pre-run.json`.
- All 40 QA save files matched the existing witness before launch and after the run; zero differences. No original save was edited.

## Visual sequence and evidence

Evidence directory: `D:\QA-Storage\fable2-active\evidence\f5diag-visual-step-20261115T004909Z`.

1. Before input, the focused game window showed the title prompt `Pulsa A para empezar` (game-player capture, local clock 19:49:43). This was a title screen, not attract or menu.
2. `pad a 10` was archived byte-for-byte and injected at `2026-11-15T00:50:31.8245170Z`; `inputs.jsonl` records the SHA-256.
3. The next captured image (local clock 19:50:49) showed attract scenery with `Pulsa E para empezar`. It did not show the main menu, so the sequence stopped there without a down/confirm input.
4. After a 6-second wait, the next `game-player.look` could not find the Fable window. The shell tool reported its 120-second timeout although the child guard had a 180-second timeout. At post-timeout inspection, the recorded guard/game PIDs 33712/36668 and the Fable window were absent; normal guard completion/termination metadata was not captured. The stale record was later reconciled to `interrupted`; the original `running` record is preserved as `run.json.pre-reconcile`.

The process log is archived as `game-log-as-run.txt`; guard/runtime metadata and save hashes are in `post-run.json`; the visual sequence is in `visual-observations.md`. Do not treat any frame-event trace values as unique FPS.

## Nested-timeout diagnosis and recovery

- **Observed mechanism:** the guarded run was configured for 180 seconds, but the `functions.shell` call itself used `timeout=120000` and returned `Command exceeded timeout of 120000 ms`. Its run record had been written as `running` with child PID 36668; the guard PID 33712 is encoded in the guard-generated run ID. The guard's final status write occurs only after its child polling loop exits. The call-level timeout occurred first, and at the later inspection both PIDs were absent. The command log was empty and no normal guard finalization was recorded.
- **Limit of attribution:** this establishes that the caller deadline expired before the guard deadline and the process tree was gone at inspection. It does not identify the exact OS termination mechanism or prove a defect in the guard's own timeout path. Existing and new supervisor tests exercise guard-owned timeouts, not host-side forced termination.
- **Honest stale-record recovery:** `qa_storage_guard.py reconcile-stale --run-id <exact-id>` is dry-run only. Add `--apply` only for a reviewed, exact run ID. It checks that supervisor and child PIDs are absent, saves the original bytes as `run.json.pre-reconcile`, and marks the current record `interrupted` with cause/exit code unknown. It intentionally does not invent `ended_utc`, return code, or `termination_verified`. The interrupted record for this run was applied after its dry-run candidate was observed; exact original SHA-256 is `929669b5d6ce6e6b4a97e9dfcabc8b239a24841f112745ff093e984b2a755b71d`.
- **Future nested deadlines:** when guard timeout is 180 seconds, give the host tool at least 240 seconds (`functions.shell` timeout `240000` ms); for the documented 300-second gameplay handoff, use at least `360000` ms. Keep at least 60 seconds for guard shutdown and final JSON write. If the host cannot grant a deadline above the child guard, do not launch that long run; lower the guard timeout or use a host runner with a longer deadline.
- **Next concrete step:** in a later authorized visual session, launch the copied QA tree with guard timeout 180 seconds and host timeout 240000 ms. Observe title/attract/menu after each single input; proceed only after a confirmed menu, then gameplay. If it does not transition, stop before further navigation. Submit `f5diag` only after gameplay is visibly confirmed and capture its contemporaneous `console/out.txt` response.

## Cleanup and verification

- The as-run `console/state.txt` snapshot (SHA-256 `b6c485c1d1935f85978770540e09f604eda52e4303c01233c81a7a089f8cba7f`) is retained. Because preservation of the pre-run state was explicitly requested, `console/state.txt` was restored from the exact pre-run backup (SHA-256 `c81428c0d5105683d695662e18d0e20efaf36d400dd9ca95bea194e632cda497`).
- The two staged Lua files, `console_pump.lua`, and `console/out.txt` were restored byte-for-byte to their pre-run copies. `console/in.txt` and `console/run.tmp` are absent.
- The run did not reach gameplay. `f5diag` output, sampler registration, and sampler behavior were not verified. The title/attract transition is an observation only, not a finding about input dispatch or causality.
