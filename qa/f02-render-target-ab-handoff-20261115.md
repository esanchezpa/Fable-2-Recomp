# F-02 render-target optimization: bounded A/B handoff

## Decision

Select F-02 (`faster_render_targets`) as the next isolated performance validation. Do not port another implementation: the candidate is already present in the pinned ReXGlue SDK (`d6a2acfc`) and is enabled in the project config. No code change is justified until a controlled run shows that the existing optimization regresses or fails to activate. The prior `33 → ~57` claim at 2x is historical author evidence only; this handoff does not adopt it as a current benchmark result.

## Exact implementation and dependencies

- `thirdparty/rexglue-sdk/src/graphics/d3d12/command_processor.cpp`: `IsDepthClearRectangle` is checked in the D3D12 draw path. When `skip_depth_clear_transfers` and `execute_unclipped_draw_vs_on_cpu` are both enabled and the predicate matches, it removes the depth-transfer list before the render-target cache processes transfers/resolve clears.
- `config/fable2_config.toml` and the matching embedded template in `src/core/fable2_config.cpp`: `[patches] faster_render_targets = true` seeds both SDK cvars. Setting it false is the single A/B toggle; it restores the SDK defaults for this feature pair.
- Dependencies: Windows D3D12 path and the matching F-02 SDK code already in the pinned submodule; no new library or package. Do not test this as a Vulkan optimization.

## Spain compatibility risk

The predicate is language-independent, but its safety depends on actual draw state and the bounds inferred by `DrawExtentEstimator`, not on language. Spanish GOTY runtime compatibility has not been empirically validated for this optimization. In particular, the audit notes that the rectangle predicate checks `min_y` but not `max_y`; this is not proof of a defect, but any depth corruption, missing geometry, purple band, or visual mismatch in the ON variant is an immediate rollback. Verify the QA clone's XEX identity before the pair and leave original game files untouched.

## Why this candidate, not the other audited work

- F-03's CPU terrain/skinning evaluators are already in the pin and enabled by default; their shader-hash dispatch and Spanish GOTY activation are not confirmed, so a source port would duplicate existing code.
- F-04 adds `WakeByAddressAll`, but the audited runtime has no matching `WaitOnAddress` waiter; alone it does not remove a production spin/wait.
- F-05a/b are not in the pin, introduce cross-thread D3D12 command recording with documented `DEVICE_HUNG` lifecycle hazards, and the reported warm-cache FPS comparison was neutral. They need broader lifecycle testing before any port.
- F-06 needs the external prebuild list staged beside the executable and a Spain-data/hash parity gate; it has no local cold-start benchmark. It is not the lowest-risk next step.
- The existing `docs/FPS_CAP_INVESTIGATION.md` says `Yield_82CBD098`'s ~150M calls had negligible duration and did not limit the main-loop cadence. That conflicts with the ~13.7% CPU attribution in `docs/hotfunc_overrides.md`; therefore yield batching is not selected without resolving the difference in profiler context.

## One bounded A/B protocol (no sampler, no PresentMon, no ETW)

1. Before any launch, inspect for an existing Fable/guard process; never start a second instance. Use only a disposable D:-managed QA clone. Preflight available storage. Hash and preserve the clone's `fable2_config.toml`, all 40 save files, and `data/dir.manifest`; do not use or modify original saves.
2. Confirm Release EXE/DLL hashes are identical between A and B, D3D12 is selected, Spanish GOTY XEX SHA-256 is `6422e22327b576f6d188206ab00112eedc780f3d130a45ca6ac42f7e4b99da6c`, internal resolution is 2x, and power/display settings remain fixed. Use the same existing save and the same visually confirmed Old Bowerstone start/camera.
3. A = `faster_render_targets=false`; B = `true`. Change only that key in the disposable clone, restart between variants, confirm the `[fable2-config] loaded` startup message and absence of missing-cvar warnings, and preserve a hash of the exact config used for every run. Run three paired 60-second windows in alternating order (A/B, B/A, A/B). Use the same visually confirmed gameplay scene and safe, repeatable camera/movement pattern; omit loading, menus, observation pauses, and screenshot capture from timed windows.
4. During each window, collect **external** 1-second Windows `GPU Engine\Utilization Percentage` samples for the exact game PID (all its 3D/copy engines) and take process CPU-time snapshots at the start and end (`(Get-Process -Id $gamePid).CPU`). The GPU Engine counter set was present during preparation. This avoids in-process Lua sampling and avoids the previously invalid PresentMon/WPR paths. Save raw samples and QPC window boundaries outside the game clone.
5. Compare paired medians for per-process GPU-engine utilization and CPU seconds per wall-second. These are resource-cost metrics, not FPS. Interpret lower utilization as reduced work only alongside unchanged visual output and no rendering defect; do not call it higher FPS or better displayed-frame cadence. Keep the feature only if the reduction is repeatable beyond the run-to-run spread; otherwise call it neutral/inconclusive and do not claim a win. Discard a pair if scene/route/config differs, the counter is missing, the game crashes, or saves/config/manifest do not restore to their pre-run hashes.
6. After the final run, restore the config byte-for-byte, verify all 40 save hashes and the manifest, close the process under the storage guard, and record the actual outcome. A repeatable reduction beyond run-to-run spread with visual parity supports a resource-efficiency result only. If neutral/inconclusive, keep the existing project default unchanged and make no performance claim. If a visual regression appears, disable F-02 in the QA clone and report it for an explicit source/config decision; do not silently change the default.

## Test gate and stop condition

No source behavior changed, so no unit test is appropriate for this handoff. Existing audit found no unit target that invokes the production D3D12 depth-clear predicate; a synthetic duplicate would not validate it. The visual A/B is the required integration gate. Stop after this single three-pair campaign; do not add another sampler or extend diagnostics unless the result identifies a concrete regression.
