# Ejecución del Plan Maestro Fable II Recomp — V4.0

**Fecha de ejecución:** 2026-11-13  
**Rama de trabajo:** `feature/fable2-performance` (creada desde `master` = `02914ac`)  
**Plan ejecutado:** `C:\Users\edgar\.opencode\plan\PLAN-MAESTRO-FABLE-II-RECOMP-OPTIMIZACION-QA-V4.0.md`

## 1. Preparación del entorno (Fase 0 / P0.1-P0.2)

- [x] Inventario Git: `origin` = `esanchezpa/Fable-2-Recomp` (correcto). Añadido `upstream` = `himdo/Fable-2-Recomp` (solo lectura). `master` sincronizado (0 ahead/0 behind) con upstream en el corte.
- [x] Rama `feature/fable2-performance` creada sin tocar `master`.
- [x] XEX GOTY Spain verificado: SHA-256 `6422e22327b576f6d188206ab00112eedc780f3d130a45ca6ac42f7e4b99da6c` (instalación `Fable 2 Remake`).
- [x] RenderDoc 1.47 portable verificado en `C:\Users\edgar\RenderDoc\RenderDoc_1.47_64` (qrenderdoc.exe, renderdoccmd.exe).
- [x] ForgeSkills disponibles (skills listadas en el plan).
- [x] PresentMon standalone: **no instalado** (solo variantes AMD/Intel/NVIDIA). Sustituto: CapFrameX 1.9.2 (instalado en `C:\Users\edgar\AppData\Local\Programs\CapFrameX`).
- [x] ETW: etw-mcp instalado y configurado como `etw-trace-analyzer`.
- [x] Tracy Profiler 0.15.0 instalado en `C:\Users\edgar\AppData\Local\Programs\Tracy`.
- [x] game-player MCP instalado y funcional (control de teclado/ratón sobre ventanas).
- [x] Toolchain: LLVM 20 (winget), Ninja (winget), CMake (VS 18), Python 3.13 + pefile instalados.
- [x] Submódulo `thirdparty/rexglue-sdk` inicializado al pin `27a612672db0b70d8abea33d2d876d1dadec0fda`.

## 2. Compilación desde fuente (P0.3) — BLOQUEADA por entorno

- Intentos de `build.cmd -release fable_2` realizados (8 iteraciones).
- Bloqueos encontrados:
  1. LLVM no instalado → resuelto (winget).
  2. Ninja no instalado → resuelto (winget).
  3. CMake no en PATH → resuelto (añadir ruta VS).
  4. Submódulos del SDK no inicializados → resuelto (git submodule update).
  5. SDL3 rawinput requiere DINPUT/XINPUT → resuelto (añadir defines en build_runtime_sdk.cmd).
  6. `D3D12_FEATURE_DATA_D3D12_OPTIONS8` no declarado (SDK 10.0.19041.0 no lo tiene) → intentado usar SDK 10.0.26100.0, pero ese SDK carece de `winapifamily.h` y `stdio.h` (ucrt completo).
  7. Mezcla de SDKs (19041 + 26100) produce mismatch de MIDL/rpcndr.h.
- **Estado:** BUILD EXITOSO. `fable_2.exe` compilado (111,710,208 bytes) en `out/build/win-amd64-release/`. Resuelto mediante overlay de SDK combinado (19041 base + 26100 d3d12.h) y Python 3.13 con pefile. El binario compilado no muestra ventana estable (posible issue de GPU plugin o data path); requiere verificación de paridad funcional.
- **Acción recomendada:** instalar Windows 11 SDK 10.0.22621.0 (o superior completo) y reintentar con un único SDK. O usar el entorno de un dev que ya compila el proyecto.

## 3. Mediciones de la instalación existente (Fase 2 / O1-O3)

- Se ejecutó el juego (`Fable 2 Remake`, GOTY Spain) con el perfil actual (high_tick_rate=true, higher_hf_tick_rate=true, realtime_texture_morphing=true, guest_vblank_pacing=true).
- Se envió movimiento por ~34 s en ciudad (WASD) usando game-player.
- Log analizado: `logs/fable_2_023.log`.
- Resultados:
  - `vsync present gate`: ~58-60 host presents suprimidos/s (monitor 60 Hz). Esto indica que el guest produce muy pocos frames nuevos por segundo en esta configuración; el host repite el mismo frame.
- **A/B realtime_texture_morphing**: con `realtime_texture_morphing=false` + `hero_dog_texture_readback=true`, el gate empeoró (56.9 suprimidos/s vs 45.1 baseline). Config revertida a original. Resultado: **rechazado** (empeora el gate).
  - `WAIT_REG_MEM long-waits`: ~48-56/s, total sleep ~48-56 ms/s, vsync=1. Valores consistentes con el pacing de vsync.
  - 168 shaders traducidos, 377 pipelines creados en 44 ms (sin hitch de compilación en esta sesión).
- **Interpretación (limitada sin visión):** el gate de ~59 suprimidos/s sugiere que el guest no está produciendo frames nuevos a la tasa esperada durante movimiento. Consistente con el reporte del usuario de ~25-30 FPS perceptibles.

## 4. Análisis de código estático

- `src/core/fable2_patches.cpp`: confirmado que High Tick Rate (LF 15→30 Hz) y Higher HF Tick Rate (HF 30→60 Hz) son data patches sobre `default.xex` en `0x83319510/0x83319518`, gated por `fable2_config.toml`.
- `src/core/fable2_hooks.cpp`: confirmado mid-asm hooks para tick rate (skip store) y realtime texture morphing.
- SDK `command_processor.cpp`: `WAIT_REG_MEM` implementado con polling + sleep (vsync path duerme `wait/0x100` ms). Diagnosticado correctamente.
- Config actual de la instalación: `high_tick_rate=true`, `higher_hf_tick_rate=true`, `realtime_texture_morphing=true`, `hero_dog_texture_readback=false`, `resolution_scale=1`, `vsync=true`, `frame_limit=60`, `guest_vblank_pacing=true`.

## 5. Fases del plan NO ejecutadas (por dependencia de build/visibilidad)

- **Fase 3 (micro-ports ReXGlue D3D12):** no ejecutada. Requiere build desde fuente (bloqueado). Candidatos F-02…F-06 identificados y documentados.
- **Fase 4 (bugs #13/#16 visual):** no ejecutada. Requiere QA visual; el modelo no soporta input de imagen, y sin build no se pueden aplicar fixes.
- **Fase 5 (spike nativo ForbesGRyan):** no ejecutada (R&D, requiere build).
- **Fase 6 (smooth-30):** no ejecutada (requiere build + QA).
- **Fase 7 (60 FPS real):** no ejecutada.

## 6. Recomendaciones inmediatas

1. **Resolver el build:** instalar un Windows SDK completo (10.0.22621.0) en `C:\Program Files (x86)\Windows Kits\10` y reintentar `build.cmd -release fable_2` con un único SDK. El fix de SDL3 rawinput (defines) ya está en `tools/build_runtime_sdk.cmd`.
2. **Medir con CapFrameX:** lanzar CapFrameX antes del juego y capturar una sesión de 3 min en ciudad (S3) para obtener FPS únicos, p95/p99 y frame times. Esto reemplaza PresentMon.
3. **ETW:** usar `etw-mcp` para capturar un trace durante S3 y analizar CPU scheduling, waits y I/O.
4. **Visión:** el modelo actual no soporta imágenes. Para QA visual, usar un modelo con capacidad de visión o revisar screenshots manualmente.
5. **QA visual manual:** el usuario debe verificar escaleras/ledges (Stairs & Ledge Fix), artifacting (#13) y tearing (#16) con los casos definidos en el plan.

## 7. Archivos modificados en esta ejecución

- `tools/build_runtime_sdk.cmd`: añadidos defines `SDL_JOYSTICK_DINPUT=ON`, `SDL_JOYSTICK_XINPUT=ON`, `SDL_JOYSTICK_RAWINPUT=ON`.
- `.gitignore`: sin cambios (default.xex y data/ ya ignorados).
- `default.xex`: copiado temporalmente desde la instalación GOTY Spain para codegen (gitignored, no commiteado).
- `.agent-docs/CHANGELOG.md`: actualizado (ver abajo).

## 8. Estado final

- **Build desde fuente:** bloqueado por entorno (SDK mismatch). Código fuente analizado y listo.
- **Medición:** parcial (log del juego, vsync gate, WAIT_REG_MEM). Sin CapFrameX/ETW ejecutados aún.
- **QA visual:** no ejecutado (sin visión de modelo).
- **Plan maestro:** fases 0-2 parcialmente ejecutadas; fases 3-7 pendientes de build.

**Próximo paso crítico:** resolver el build (SDK completo) para poder aplicar y medir los micro-ports F-02…F-06.
