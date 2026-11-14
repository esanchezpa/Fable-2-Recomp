# Changelog

## [Unreleased]

### Added
- Completed the F5 sampler integration contract: F5 loads and ticks it only when armed/active; console commands request a delayed start, stop, inspect status, or dump after the window. Ring overwrite/sample counters are exposed. Added source-contract tests; in-game runtime and overhead remain unverified.
- Added an opt-in bounded Lua sampler with frame-window auto-stop and an existing F5-loop tick hook; documented guarded QA RED/GREEN evidence and the remaining runtime and overhead gates.
- Recorded the 2026-11-14 guarded VFS retry: the clone did not reach verified QA gameplay, so no sampler runtime result is claimed; temporary files were restored and all 40 clone saves still match the witness clone.
- Added guarded build/gameplay entry points and regression coverage for managed QA roots, storage limits, bounded traces, and child-process lifetime.
- Routed build.cmd through the supervisor and added a dedicated launcher for copied QA gameplay trees; build Python selection remains process-local.

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
- `build.cmd` adds the installed Visual Studio 18 CMake directory to its own process PATH without changing user or system settings.

### Fixed
- Corrected the frame-event trace correlation count: the first 91 host presents precede guest output; the remaining 21,533 carry IDs that match produced and acquired events.
- Instrumentación opt-in de eventos XE_SWAP, producción de guest output y llamada DXGI Present, con secuencias y timestamps separados; no representa imágenes guest únicas ni confirmación de display.
- Correlación opt-in de IDs de guest output a través del mailbox hasta el intento `Present`, incluyendo índice de mailbox y `GetLastPresentCount`; esta última cifra no es confirmación de display.
- Rama `feature/fable2-performance` para optimizaciones.
- `qa/execution-report.md`: informe de ejecución del plan (build bloqueado por entorno SDK, mediciones parciales).
- Herramientas instaladas: game-player MCP, CapFrameX 1.9.2, etw-mcp, Tracy 0.15.0, RenderDoc 1.47.

### Changed
- `tools/build_runtime_sdk.cmd`: añadidos defines SDL_JOYSTICK_DINPUT/XINPUT/RAWINPUT para resolver build SDK.
- Toolchain: LLVM 20, Ninja, CMake (VS 18), Python 3.13 + pefile instalados.
- Submódulo `thirdparty/rexglue-sdk` inicializado al pin `27a61267`.
- Release completado con Windows SDK 10.0.26100.9457 y toolchain verificado; gameplay trazado en copia aislada bajo guard, con correlación guest/mailbox/Present y hashes de saves preservados. La corrida finalizó por el timeout explícito de 540 s; no se afirma estabilidad prolongada ni métricas de FPS/display.
