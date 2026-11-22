# Pruebas y cobertura

La suite está dividida en niveles. Todos son deterministas: usan video sintético,
fakes y zonas generadas en `tmp_path`; no necesitan RTSP, GPU ni internet.
G0 instrumenta el pipeline actual (un proceso / una cámara / ReID local) sin
activar ejecución multi-cámara; ver [g0-baseline-plan.md](g0-baseline-plan.md).

| Nivel | Selección | Qué cubre | Dónde corre |
|---|---|---|---|
| Smoke | `python -m pytest -q -m smoke` | Pipeline de 35 frames con umbral de rendimiento amplio | Cada PR (`ci.yml`, job `smoke`) |
| Unidad | `python -m pytest -q -m "not slow"` | DTOs, mappers, casos de uso, puertos y reglas de arquitectura | Cada PR (`ci.yml`) |
| Integración | incluida en el comando anterior | Pipeline completo con `create_pipeline_sample`, detector/ReID fakes, zonas, eventos reales y baseline `camera_id`/p50/p95 | Cada PR (`ci.yml`) |
| E2E | `python -m pytest -q -m slow` | Monitor HTTP real: estado, eventos, personas, métricas etiquetadas y frames sobre archivo; baseline de 30 s | Nightly o manual (`e2e.yml`) |
| Rendimiento | `python -m pytest -q -m performance` | Presupuestos, regresiones, generador sintético y baseline | Cada PR; benchmark completo en `benchmark.yml` |

No existe una carpeta `scripts/` versionada en la raíz: el generador vive en
`vision_core.scripts.create_pipeline_sample` y produce `sample.avi` y `zones.json`
en un directorio nuevo. Las fixtures de `tests/conftest.py` lo invocan una vez por
sesión y comparten las zonas; cada test recibe una fuente de video propia.

## Comandos locales

```bash
python -m pip install -r requirements.txt
python -m pip install -e .

# Unidad + integración con cobertura (igual que el job de PR)
python -m pytest -q -m "not slow" \
  --cov=vision_core --cov-branch \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-report=json:coverage.json \
  --cov-report=html:htmlcov \
  --cov-fail-under=80
python -m vision_core.scripts.check_coverage coverage.json

# E2E pesado (igual que el job nightly)
G0_PROFILING_ARTIFACT=profiling_results.json python -m pytest -q -m slow

# Selección por nivel
python -m pytest -q -m smoke
python -m pytest -q -m integration
python -m pytest -q -m performance

# Benchmark nocturno y baseline
make benchmark

# Suite completa, incluyendo e2e
python -m pytest -q
```

## Umbrales de cobertura

El reporte global incluye ramas y excluye `vision_core/scripts/` (herramientas de
diagnóstico). El job de PR falla si la cobertura global baja de 80% o si algún
módulo crítico baja de su umbral:

| Módulo | Patrón | Umbral |
|---|---|---|
| `pipeline` | `/features/pipeline/` | 90% |
| `door` | `/features/door/` | 80% |
| `monitor` | `/features/monitor/` | 85% |
| `features` | `/features/` | 85% |
| `core_domain` | `/core/domain/` | 90% |
| `core_errors` | `/core/errors/` | 90% |
| `core_config` | `/core/config/` | 85% |
| `core_serialization` | `/core/serialization/` | 80% |
| `core_persistence` | `/core/infrastructure/persistence/` | 80% |
| `observability` | `/core/telemetry/` | 85% |
| `profiling` | `/core/inference/frame_profiler.py` | 90% |
| `global` | `vision_core` sin scripts | 80% |

`python -m vision_core.scripts.check_coverage coverage.json` imprime el valor de
cada módulo y termina con código 1 si alguno no alcanza su umbral. La definición
está en `src/vision_core/scripts/check_coverage.py`.

## Integración

`tests/integration/test_synthetic_video_pipeline.py` genera el video y las zonas
con `create_pipeline_sample`, reproduce 35 frames e inyecta detecciones fijas
cruzando exterior → interior → exterior → fuera. Verifica:

- secuencia de eventos `PERSON_ENTERED`, `PERSON_EXITED`, `FALSE_ALARM`,
  `PERSON_ENTERED`, `PERSON_EXITED`, con `from_zone`/`to_zone`;
- identidad estable, incluida la recuperación tras pérdida de track;
- historial de zonas y personas por frame;
- cierre limpio de la fuente de video al terminar.

`tests/integration/test_g0_baseline.py` usa la misma muestra con profiling
activado y `camera_id="camera-g0"`. Comprueba que el JSON contenga esa etiqueta,
35 frames, las seis etapas de `FrameProfiler.STAGES` y p50/p95 por etapa, además
de la secuencia de eventos y el cierre limpio.

No se comprueban timestamps exactos: los eventos solo deben ser finitos.

`tests/performance/test_performance_smoke.py` reutiliza la misma muestra para
ejecutar el pipeline real con `pr-smoke` y verificar FPS, latencia, memoria y
serialización con umbrales amplios. `tests/performance/test_benchmark_analysis.py`
inyecta una regresión artificial de FPS y p95 para demostrar que la comparación
contra baseline funciona; una fluctuación pequeña no se marca como regresión.

## E2E

`tests/e2e/test_monitor_e2e.py` usa la misma muestra, carga `zones.json` real desde
el composition root (`main.build_monitor_pipeline`) y levanta un
`ThreadingHTTPServer` en `127.0.0.1:0`. Valida `/`, `/api/state`, `/api/frame`,
`/api/frame?after=35`, `/health` y `/metrics`: estado `running`, 35 frames,
eventos y contadores, persona con zona y etiqueta, JPEG con cabecera de secuencia
y métricas (`fps`, `processing_ms`, `dropped_frames`, `age_seconds`) coherentes.
Las claves de `/metrics` están agregadas y etiquetadas con `camera_id=camera-e2e`.
El detector, ReID y extractor son fakes; el video es archivo local.

`tests/e2e/test_g0_profiling_30s.py` repite la muestra local durante al menos
30 s con profiling activado para producir el baseline exigido por la puerta G0.
No usa RTSP, GPU ni internet y, si se define `G0_PROFILING_ARTIFACT`, escribe el
JSON en esa ruta para publicarlo como artefacto.

## CI y artefactos

- `ci.yml`: instala dependencias, ejecuta unit + integración con cobertura,
  verifica umbrales globales y por módulo, y sube `coverage-pr` (XML, JSON y HTML)
  siempre. En fallo sube `pytest-pr-logs`. El job `smoke` ejecuta `-m smoke`,
  publica un resumen y sube `performance-smoke.json` y `pytest-smoke.log`.
- `e2e.yml`: `schedule` diario y `workflow_dispatch` manual. Ejecuta solo `-m slow`,
  publica `g0-profiling` con `profiling_results.json` y sube `pytest-e2e-logs`
  siempre.
- `benchmark.yml`: `schedule` nocturno y `workflow_dispatch` manual. Genera video
  sintético, ejecuta el pipeline con presupuestos estrictos, compara contra
  baseline, publica el resumen en el job y sube JSON/CSV/Markdown y logs.
- El job `build` solo compila; `lint.yml` mantiene Ruff y formato.

Los presupuestos, la metodología y los hotspots están en
[performance.md](performance.md).

Las pruebas reales optativas con cámara, modelos pesados o CUDA siguen fuera de
estos jobs y se documentan en [validation.md](validation.md).
