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

## Follow-up: malformed `pad` command — 2026-11-15

- The later directed-run archive `D:\QA-Storage\fable2-active\evidence\f02-directed-20261114T211905` contains `out.txt.as-run` with the new `[pad] ERR bad frame count` line and the corresponding idle marker. The archived directory does **not** contain `console/in.txt` or an input-byte dump; `command.log` is empty. Therefore the precise bytes consumed cannot be independently reconstructed from that archive alone.
- Source explains the rejection: `split_words` tokenizes on whitespace; `pad a 10` treats the third token as the frame count; `parse_u` requires the entire token to parse as an unsigned integer; and the `pad` handler emits `bad frame count` on failure. If the staged text ended in the literal characters `` `n ``, the token would be `10` followed by those characters and would fail. A real LF or CRLF after `10` is a line delimiter and does not become part of that token. This makes the reported PowerShell literal-backtick-n staging error consistent with the output, but the missing input artifact means the bytes themselves are not independently proven.
- The `pad` handler accepts 1–100000 frames; `10` is valid. A later successful documented navigation used separate staged commands `pad a 10`, `pad down 12`, `pad a 12` (then another `pad a 12`) and reached gameplay. The failure is thus not evidence that ten frames are out of range or that the `pad` grammar rejects the command; dispatch/timing and visual state remain separate questions.
- Safe staging form for a future authorized run is a UTF-8 file without BOM containing exactly one command and a real newline, e.g. PowerShell `.NET` `WriteAllText(path, "pad a 10`n", [Text.UTF8Encoding]::new($false))`. Do not execute it until the visual run is authorized; use the established one-command/one-observation navigation sequence and stop if the screen does not match the expected transition.
- Observer correction is independent: a fixed observer duration must exceed guard timeout plus prelaunch lead (with margin), or monitor the exact child PID and stop only after it exits. The 240-second observer did not cover the full 240-second guard run.

## Runtime follow-up — 2026-11-15

- In guarded run `20261115T024555Z-27152-3b975ab5`, a fresh staged `pad a 10; echo F02_PAD_A10_ACK` was archived before publication. Exact input hash: `8F89E7D9A0CE9D05B242190C0CCE7508579DCE43CBDD10CDE1CA170C4FB47F8D`; 31 ASCII bytes, final byte LF (`0A`), no BOM. The pump consumed the file and `console/out.txt` added the unique echo marker followed by `IDLE`, providing contemporaneous evidence of command queue completion. This establishes that the corrected newline transport works; it does not retroactively prove the missing bytes from the earlier malformed attempt.
- The pad command did not immediately leave the title. The title's attract/cinematic sequence was observed across another frame, allowed to continue until the title prompt returned, then input changed based on the visible prompt and prior navigation evidence: E opened the menu, S selected “Continuar”, and E opened the existing Hero 1 save card.
- The final confirmation action was refused because the matching game window had disappeared at the guard's 300-second timeout (return 124, child termination verified). No more input or relaunch followed; gameplay and F-02 cvar reads remain unverified. Observer coverage ran from prelaunch through guard termination. The evidence and exact restoration checks are in `qa/f02-render-target-ab-handoff-20261115.md` under “Visual follow-up — 2026-11-15”.
