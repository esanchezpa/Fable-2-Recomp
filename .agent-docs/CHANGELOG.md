# Changelog

## [Unreleased]

### Added
- Plan maestro V4.0 de rendimiento y QA (`PLAN-MAESTRO-FABLE-II-RECOMP-OPTIMIZACION-QA-V4.0.md`).
- Rama `feature/fable2-performance` para optimizaciones.
- `qa/execution-report.md`: informe de ejecución del plan (build bloqueado por entorno SDK, mediciones parciales).
- Herramientas instaladas: game-player MCP, CapFrameX 1.9.2, etw-mcp, Tracy 0.15.0, RenderDoc 1.47.

### Changed
- `tools/build_runtime_sdk.cmd`: añadidos defines SDL_JOYSTICK_DINPUT/XINPUT/RAWINPUT para resolver build SDK.
- Toolchain: LLVM 20, Ninja, CMake (VS 18), Python 3.13 + pefile instalados.
- Submódulo `thirdparty/rexglue-sdk` inicializado al pin `27a61267`.

### Blocked
- Build desde fuente: bloqueado por mismatch de Windows SDK (10.0.19041 vs 10.0.26100). Requiere SDK completo.
- QA visual: modelo no soporta imágenes.
