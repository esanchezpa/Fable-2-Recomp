# Changelog

## [Unreleased]

### Changed
- Added exact-run stale-record reconciliation for externally interrupted QA supervisors; snapshots the original record and records process absence without fabricating exit codes, end time, or verified termination. Added supervisor PID metadata, regression tests, and host-timeout margins to the gameplay handoff.
- Recorded a bounded visual input check: one title-screen pad input was followed by an attract-scene image, with no menu/gameplay transition; the shell timeout prevented normal guard finalization, while saves and restored QA state/scripts were verified.
- Added an offline comparison of the guarded title-screen input attempt with the prior staged-pad gameplay navigation; recorded the limits of the evidence and a visual validation hypothesis without assigning cause.
- Resolve the optional sampler from the shared Lua global on every persistent F5 updater frame, allowing a later F5 evaluation to publish it after an earlier load attempt; add a source-contract regression check. Runtime gameplay validation remains pending.
- Documented RenderDoc PATH injection evidence: three WER crashes name `renderdoc.dll_unloaded`, A/B guard runs show crash with RenderDoc in PATH vs 60 s stability without it, no IFEO/AppInit/global hook, and a controlled test protocol that varies only the child PATH without system changes.
- Recorded the guarded `f5diag` runtime attempt: the clone remained at title/menu, the console pump explicitly dropped the command before invoking its handler, WER startup crashes named `renderdoc.dll_unloaded` without persistent dumps, and restoration verified all 40 QA saves plus the manifest; no sampler cause is inferred.
- Added opt-in F5 load diagnostic: F5.lua now captures loadfile/pcall results and stores them in `__f2_f5_load_diag`; console command `f5diag` exposes them on demand. TDD source-contract tests added (9/9 pass). No behavior change to F5 or sampler; runtime QA still pending under guard.
- Matched the 11:01:23 WER fast-fail to guarded run `20261114T160002Z-40544-4272598a`; documented the later observer-deadline runs, Release F5 logging limitation, and verified QA save/manifest restoration without attributing the crash to Lua or the sampler.
- Reached gameplay via console pad navigation and confirmed the max-saves dialog blocks Continue; F5 via window_post crashed the process; sampler remains unavailable; restored all 40 saves and clone state.
- Reached QA gameplay through console pad navigation (title -> Continue -> load save -> Old Bowerstone) and opened the F5 menu; sampler stayed unavailable after F5, so arming, movement, dump, and overhead remain unverified; restored clone state and all 40 saves.
- Added concurrent passive Win32 PID/HWND/session/focus observation for the guarded QA clone, confirming a visible foreground game window during life of the process; title navigation still did not reach the menu, so sampler activation and overhead remain unverified.
- Corrected and retained the observer's no-visible-window cutoff after its first run exposed a false cutoff despite visible HWND samples; restored the QA console state and verified the EXE, manifest, protocol files, and all 40 saves against their pre-run witnesses.
- Added symbol-backed evidence for a first-chance AV during startup (invalid write in the Fable render loop), while documenting the ntdll symbol mismatch, repeated first-chance handler/log flood, guarded timeout, and that no fatal gameplay AV/root cause was established.
- Recorded the guarded profiler/CDB gameplay run: matching private PDB symbols loaded, the save reached gameplay, only first-chance access violations were logged, no crash dump or unhandled failure occurred before the 540-second watchdog, and the QA executable, manifest, and all 40 saves were restored/verified.
- Documented the guarded menu-navigation diagnosis: the game window was focused, `E` mapped to A, `Down` did not move the menu, `S` (StickDown) selected Continue, and the existing save reached gameplay; all 40 QA save hashes remained unchanged.
- Recorded the profiler/CDB capture timing out at the title screen, restored the disposable QA clone from preserved pre-run files, and verified all 40 save hashes unchanged; no crash dump or causal finding was available.
- Documented the guarded no-sampler/no-trace CDB launch: it captured a second-chance AV but no fast-fail, exposed a Release PDB/QA EXE identity mismatch, and preserved all 40 saves; the A/B and root cause remain unproven.
- Recorded why the historical no-sampler QA clone is not a causal baseline and the CDB availability blocker; traced and fixed the PE version-resource helper's unclosed DLL handles, with a regression test and clean full-suite run.
- Recorded the safe D:-only GOTY Spain launch-root verification, preserved a guarded fast-fail investigation, and documented that the sampler/movement gates remain unverified.
- Documented the verified MSVC 14.51/14.44 linker mismatch and successful guarded Release build using process-local MSVC 14.44 and staged Windows SDK paths.
- Identified the verified F-06 source in gitgudscrub/Fable-2-Recomp, added a pure-Python parser and 12 contract tests for shader_prebuild.txt, and updated the QA report; no runtime, SDK pin, assets or game data were changed.
- Fixed atlas test discovery under the documented unittest command, added a synthetic no-overwrite regression, and documented the F-04 wake test matrix and missing waiter dependency.
- Corrected the SDK candidate mapping and recorded source, pin, license, test coverage, and Spain-compatibility limits for F-03 through F-06.
- Ampliada la revisión de F-02 contra su parent real, la base descendiente `27a6126` y SDK HEAD; documentados predicados, dependencias, ausencia de pruebas GPU y el supuesto de altura que requiere reproducción. No se cambia la lógica ni se presume compatibilidad Spain.
- Documentado el cotejo del commit oficial F-02 `80e0b5cf` con el SDK actual: código presente y licencia BSD-3-Clause intacta; no hay prueba unitaria dedicada ni validación runtime Spain porque game-player MCP está desconectado.
- Añadido al informe QA el análisis offline de ambos minidumps con CDB/WinDbg oficial, el contexto de excepción y las limitaciones de atribución; no se aplica un parche sin causa raíz demostrada.
- Documentada la comparación QA OFF/ON con watchdog y protección hash de los 40 saves; una AV `0xC0000005` ocurrió cerca de F5 en la corrida ON, pero sin dump ni control F5 OFF válido no se atribuye a una causa ni se aplica un parche.
- Registrado que el control OFF+F5 agotó el watchdog antes de alcanzar el mismo save/modal y que los 28 tests independientes de sampler contract, replay/QPC y storage guard pasan; runtime y causalidad siguen sin demostrarse.
- Añadido diagnóstico del último arranque fallido: el log llega al attract del título, pero no registra input/foco; el canal remoto Debug no estaba presente en los clones Release. Auditoría de solo lectura de hashes/logs del reemplazo de iconos sin reproducir el defecto ni cambiar fuentes/arte.

### Added
- Added six static contract checks for console file ingestion, lazy Lua-pump startup, ready/done sequencing, output routing, and the distinct 20 s startup-drop and 30 s reply-timeout paths. Guarded tests pass; this does not establish which path occurred in a prior runtime attempt.
- Documentada la auditoría estática de tres commits ReXGlue (memexport CPU, límite de presents y sync GPU) y ejecutado bajo guard el test nativo de `PresentRateLimiter`; la correspondencia F-03/F-04/F-05 queda marcada provisional porque falta la lista maestra.
- Añadida herramienta read-only para inspeccionar atlas/sidecar KBPM v2 con detiling A2/Xenos y comparación byte a byte con bancos GOTY Spain, cubierta por siete pruebas sintéticas.
- Incluido `thirdparty/rexglue-sdk/out` en el presupuesto de almacenamiento administrado y añadida una prueba de regresión; las builds del SDK ya no quedan fuera del límite del guard.
- Registrada la revalidación QA del sampler del 2026-11-14: el clon cargó el save existente, pero dos procesos terminaron con excepciones nativas antes de obtener un resultado actual verificable del sampler; los 40 saves permanecen iguales al testigo.
- Completed the F5 sampler integration contract: F5 loads and ticks it only when armed/active; console commands request a delayed start, stop, inspect status, or dump after the window. Ring overwrite/sample counters are exposed. Added source-contract tests; in-game runtime and overhead remain unverified.
- Added an opt-in bounded Lua sampler with frame-window auto-stop and an existing F5-loop tick hook; documented guarded QA RED/GREEN evidence and the remaining runtime and overhead gates.
- Recorded the 2026-11-14 guarded VFS retry: the clone did not reach verified QA gameplay, so no sampler runtime result is claimed; temporary files were restored and all 40 clone saves still match the witness clone.
- Added guarded build/gameplay entry points and regression coverage for managed QA roots, storage limits, bounded traces, and child-process lifetime.
- Routed build.cmd through the supervisor and added a dedicated launcher for copied QA gameplay trees; build Python selection remains process-local.
- Added an S3 replay planner and QPC-window trace summarizer with bounded, source-level test coverage; these tools do not certify a safe route or FPS/display rate.
- Updated package-release fixtures to expect the already-bundled keycap font and its license in the archive.
- Aligned the native keyboard/gamepad test stub with the focused `poll_f5(bool)` interface.
- Recorded passing guarded native tests and incremental Release link with the installed MSVC 14.44 toolset; the sampler VFS/runtime and campaign-performance gates remain open.
- Corrected the in-game sampler test to shadow GameFace's metatable-backed `QuestManager` global without mutating the engine hero object.
- Made the in-game sampler test restore its prior ring and counters, so its capacity-3 assertion does not leak into later QA sampling; the sampler source-contract suite now covers this cleanup.
- Added a guarded SDK frame-event trace that distinguishes guest swaps, guest-output production/acquisition, and DXGI present attempts without treating any of them as proof of displayed frames.

### Fixed
- Sincronizado el stub de `poll_f5` del test nativo con el parámetro `focused` de la interfaz real.
- La traza opt-in exige una ruta absoluta nueva y usa creación exclusiva para no truncar archivos existentes; el test verifica preservación del archivo previo.
- Removed the account-specific Python path from `build.cmd`, allowing CMake's interpreter selection or an explicit cached interpreter.
- Updated release-package test fixtures and archive expectations for the bundled font and license.
- Recorded an isolated GOTY Spain city-load and movement smoke test, with before/after hashes of the original saves and explicit remaining QA gaps.
- Compared the same copied save and short movement sequence against a separately isolated reference build; documented the limited scope and outstanding parity checks.
- Recorded a QA-only save/reload, per-process audio signal measurements, and unsuccessful PresentMon diagnostics without treating host presents as unique frames.
- Documented the distinct XE_SWAP, guest-output, gate and display semantics, including limitations of existing timing counters and ETW observations.
- Recorded paired trace-OFF/ON QA attempts, watchdog outcomes, process sampling, the ON trace's zero guest IDs on DXGI attempts, preserved source-save hashes, and the non-invasive WPR profile conflict; the comparison remains inconclusive.
- Corrected the QA report: suppressed host presents do not measure unique frames, and the previous texture-morphing A/B result is inconclusive.
- Recorded reconstruction of an isolated Spain QA copy, verified save preservation, and invalid PresentMon/WPR capture attempts with their concrete failure evidence.

### Added
- Recorded the ON city-gameplay capture, unchanged OFF/ON save hashes, and a bounded no-loss graphics ETL; PresentMon offline still produced no CSV, so unique displayed guest frames and paired performance remain unverified.
- Documented visually verified, equivalent OFF/ON S3 run/turn/camera-input sequences with timestamped screenshots, guarded runs and unchanged save hashes; the dynamic route is validated, but no overhead benchmark was captured.
- Added a short-step S3 replay planner with QPC markers and QPC-windowed event counts; the guarded ON pilot exposed repeatable wall/stall collisions, so no 180-second pass or OFF/ON overhead result is claimed. A new guarded offline PresentMon attempt again returned success without producing CSV.
- Recorded a guarded visual follow-up of the copied S3 plaza save: short movement and camera inputs, 13 hashed frames/QPC markers, unchanged ON/OFF saves, no certified safe circuit, no paired 180-second campaign, and the Debug-only remote replay/screenshot alternative with its performance-comparability limit.
- Verified the documented F5 `HeroEntity:GetPosition()` path in the guarded ON Release QA clone: coordinates changed after one short input and repeated identically at rest; hashes and save integrity were preserved. Recorded why the existing modal one-shot cannot measure sampler overhead, a reproducible waypoint procedure, and the low-rate in-memory sampler design needed before any paired overhead run; 6 replay-tool tests pass.
- D:-only QA/build storage supervisor with C:/D: free-space thresholds, managed-storage budget, per-process timeout/tree termination, redirected temp/caches, bounded generic log/trace monitoring, evidence-preserving cleanup, and WPR/ETW command rejection.
- Guarded gameplay launcher for copied D: QA trees, with startup-required, size-capped frame-event CSV evidence.
- Plan maestro V4.0 de rendimiento y QA (`PLAN-MAESTRO-FABLE-II-RECOMP-OPTIMIZACION-QA-V4.0.md`).

### Changed
- Reached QA gameplay through console pad navigation (title -> Continue -> load save -> Old Bowerstone) and opened the F5 menu; sampler stayed unavailable after F5, so arming, movement, dump, and overhead remain unverified; restored clone state and all 40 saves.
- `build.cmd` adds the installed Visual Studio 18 CMake directory to its own process PATH without changing user or system settings.

### Fixed
- Corrected the frame-event trace correlation count: the first 91 host presents precede guest output; the remaining 21,533 carry IDs that match produced and acquired events.
- Instrumentación opt-in de eventos XE_SWAP, producción de guest output y llamada DXGI Present, con secuencias y timestamps separados; no representa imágenes guest únicas ni confirmación de display.
- Correlación opt-in de IDs de guest output a través del mailbox hasta el intento `Present`, incluyendo índice de mailbox y `GetLastPresentCount`; esta última cifra no es confirmación de display.
- Rama `feature/fable2-performance` para optimizaciones.
- `qa/execution-report.md`: informe de ejecución del plan (build bloqueado por entorno SDK, mediciones parciales).
- Herramientas instaladas: game-player MCP, CapFrameX 1.9.2, etw-mcp, Tracy 0.15.0, RenderDoc 1.47.

### Changed
- Reached QA gameplay through console pad navigation (title -> Continue -> load save -> Old Bowerstone) and opened the F5 menu; sampler stayed unavailable after F5, so arming, movement, dump, and overhead remain unverified; restored clone state and all 40 saves.
- `tools/build_runtime_sdk.cmd`: añadidos defines SDL_JOYSTICK_DINPUT/XINPUT/RAWINPUT para resolver build SDK.
- Toolchain: LLVM 20, Ninja, CMake (VS 18), Python 3.13 + pefile instalados.
- Submódulo `thirdparty/rexglue-sdk` inicializado al pin `27a61267`.
- Release completado con Windows SDK 10.0.26100.9457 y toolchain verificado; gameplay trazado en copia aislada bajo guard, con correlación guest/mailbox/Present y hashes de saves preservados. La corrida finalizó por el timeout explícito de 540 s; no se afirma estabilidad prolongada ni métricas de FPS/display.
