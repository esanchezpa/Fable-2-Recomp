# Handoff visual: validación runtime de `f5diag` (Luna)

Fecha: 2026-11-14. Autor: sesión Beam Free (no visual). Coordinador visual: Luna (GPT-6 medium build).

## Objetivo

Validar en gameplay real el comando de consola `f5diag` (commit `f34ff44`) en el clon QA, capturando su salida real (`loadfile_ok`, `loadfile_err`, `pcall_ok`, `pcall_err`, `sampler_registered`) y, si el sampler queda registrado, ejecutar `sampler start 1800` → movimiento del héroe → `sampler stop`/`dump`, midiendo overhead. Todo bajo `qa_storage_guard.py`, sin modificar sistema, saves ni manifest.

## Preconditions (ya verificadas)

- Clon QA: `D:\QA-Storage\fable2-active\gameplay-pair-20261113`. EXE/DLL/manifest byte-idénticos a Release; XEX GOTY Spain.
- Saves: 40/40 coinciden con testigo `f5diag-pre-run-20261114113636.json` (0 diferencias). Manifest SHA-256 `3c1e74f3ee0dd55ed336d2c4a58cfe4a849c900c1a7483c140f6c713d1cac8e8`.
- No hay proceso `fable_2.exe` ni guard activo (verificado). `computer-use` MCP sigue caído (`WinError 10061`); usar `game-player` para captura visual.
- RenderDoc está en PATH del sistema y causa crashes de arranque correlacionados (`renderdoc.dll_unloaded`, `0xC0000005`). **Excluir RenderDoc del PATH solo del proceso hijo**, sin tocar el sistema.

## Exclusión de RenderDoc (por proceso, sin cambios globales)

Lanzar el guard con `PATH` que omite `C:\Users\edgar\RenderDoc\RenderDoc_1.47_64`. En PowerShell (solo sesión actual):

**Deadline anidado obligatorio:** el guard de este comando usa 300 s. La llamada host de OpenCode debe usar `timeout=360000` ms como mínimo (300 s más 60 s para terminar el árbol y escribir el registro); no usar el timeout host predeterminado de 120 s. Si el host no admite ese margen, no iniciar el juego.

```powershell
$rd = "C:\Users\edgar\RenderDoc\RenderDoc_1.47_64"
$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -ne $rd }) -join ';'
python "D:\Fable.2.Game.of.the.Year.Edition-P2P\Fable-2-Recomp\tools\qa_storage_guard.py" gameplay `
  --repo-root "D:\QA-Storage\fable2-active\gameplay-pair-20261113" `
  --game-root "D:\QA-Storage\fable2-active\gameplay-pair-20261113" `
  --backend d3d12 --timeout-seconds 300 --trace-max-bytes 67108864
```

Verificar en el log del juego (`logs/fable_2_*.log`) que NO aparece "RenderDoc API initialized" (0 menciones). Si aparece, abortar: PATH no se propagó.

## Navegación (visual confirmar cada transición)

Ruta verificada (pad de consola, no teclado host):
1. Esperar ≥10 s tras arranque; captura: pantalla de título "Pulsa A para empezar".
2. `pad a 10` → abre menú principal.
3. Captura: menú principal.
4. `pad down 12` → selecciona "Continuar".
5. Captura: "Continuar" resaltado.
6. `pad a 12` → abre lista de saves.
7. Captura: lista de saves.
8. `pad a 12` → carga "Hero 1 / Ciudad Vieja de Bowerstone".
9. Esperar ≥5 s; captura: gameplay (OCR "1 de 5 piezas de oro").

Entrada vía `console/in.txt`: escribir una línea por comando; el pump consume el archivo. No usar Enter host.

## Secuencia f5diag

### Non-visual code update (2026-11-14)

Static source inspection found that the persistent F5 updater captured `__f2_sampler` once when the F5 chunk first loaded. A later F5 evaluation could publish the sampler table after an earlier failed load, while the persistent updater retained its original `nil` reference. This is a plausible stale-reference path, not a confirmed explanation for prior runtime behavior.

The updater now reads `rawget(_G, "__f2_sampler")` inside its per-frame loop. A Python source-contract test guards that lookup. The focused contract suite passed 10/10; the complete Python unittest suite passed 257 tests under `qa_storage_guard.py` (1 skipped, 15 expected failures). These checks inspect source/contracts and do not validate Lua execution or gameplay. Continue the runtime sequence below; do not treat `f5diag` or sampler as runtime-validated until actual in-game output and, if available, a non-empty dump are captured.

1. En gameplay estable (≥5 s tras carga), enviar F5 por `window_post` con `hold_ms=500` (el de 300 no abrió el menú de forma fiable). Verificar captura: menú "F5 Menu" con "Leave Menu", "Get Player Position", etc.
2. Cerrar con `pad a` (selecciona "Leave Menu").
3. Esperar ≥2 s (cooldown 40 frames ~0.67 s; usar 2 s para seguridad).
4. Reabrir F5 con `window_post f5 hold_ms=500`. Captura: menú "F5 Menu" de nuevo.
5. Cerrar con `pad a`.
6. Esperar ≥2 s.
7. Escribir en `console/in.txt`: `f5diag`. Capturar `console/out.txt` hasta ver:
   - `f5 load diagnostic:` ... `loadfile_ok=...`, `loadfile_err=...` (si aplica), `pcall_ok=...`, `pcall_err=...` (si aplica), `sampler_registered=...`.
8. Si `sampler_registered=true`: escribir `sampler status` → esperar acuse; luego `sampler start 1800`; conducir al héroe (WASD/pad) ~30 s; `sampler stop`; `sampler dump`. Capturar dump.
9. Si `sampler_registered=false`: registrar `f5diag` completo; NO intentar sampler; reportar causa (`loadfile_err`/`pcall_err`).

## Integridad (obligatorio antes y después)

- Antes: verificar 40/40 saves vs `f5diag-pre-run-20261114113636.json` y manifest SHA-256.
- Después: repetir verificación (0 diferencias). Restaurar `console/state.txt` desde `state.txt.before` si se modificó. Confirmar EXE/manifest hashes sin cambio. No tocar saves originales.

## Criterios de éxito (no afirmar sin evidencia)

- [ ] Arranque estable sin RenderDoc (log 0 menciones, sin crash <60 s).
- [ ] Gameplay alcanzado y capturado.
- [ ] `f5diag` ejecutado con salida real capturada (no "no F5 load diagnostic yet").
- [ ] Si sampler registrado: `sampler start/stop/dump` con dump no vacío.
- [ ] 40/40 saves + manifest verificados post-run.
- [ ] Commitear evidence + changelog solo tras éxito.

## Riesgos conocidos

- `window_post f5` crasheó en runs previos con hold_ms=300; usar 500 y esperar estabilización.
- El pump de consola solo arranca tras cargar un save; no enviar comandos antes.
- Si el menú F5 no abre, NO reintentar F5 en bucle; capturar Windows Application Error y parar.
- `computer-use` down: toda captura visual vía `game-player/look` (devuelve imagen). Si `game-player` no lista la ventana, usar el observador pasivo Win32 documentado en sección 54.

## Evidencia a conservar

- Run record `D:\QA-Storage\fable2-active\runs\<run_id>\run.json`.
- Log de juego `logs\fable_2_*.log`.
- `console/out.txt` y `console/state.txt` (before/after).
- Capturas inline (no se exportan como archivo; describir en informe).
- Hashes de saves/manifest post-run.
