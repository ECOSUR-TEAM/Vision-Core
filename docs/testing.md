# Pruebas y cobertura

La suite está dividida en niveles. Todos son deterministas: usan video sintético,
fakes y zonas generadas en `tmp_path`; no necesitan RTSP, GPU ni internet.

| Nivel | Selección | Qué cubre | Dónde corre |
|---|---|---|---|
| Unidad | `python -m pytest -q -m "not slow"` | DTOs, mappers, casos de uso, puertos y reglas de arquitectura | Cada PR (`ci.yml`) |
| Integración | incluida en el comando anterior | Pipeline completo con `create_pipeline_sample`, detector/ReID fakes, zonas y eventos reales | Cada PR (`ci.yml`) |
| E2E | `python -m pytest -q -m slow` | Monitor HTTP real: estado, eventos, personas, métricas y frames sobre archivo de video | Nightly o manual (`e2e.yml`) |

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
python -m pytest -q -m slow

# Suite completa, incluyendo e2e
python -m pytest -q
```

## Umbrales de cobertura

El reporte global incluye ramas y excluye `vision_core/scripts/` (herramientas de
diagnóstico). El job de PR falla si la cobertura global baja de 80% o si algún
módulo crítico baja de su umbral:

| Módulo | Patrón | Umbral |
|---|---|---|
| `pipeline` | `features/pipeline/` | 90% |
| `door` | `features/door/` | 80% |
| `monitor` | `features/monitor/` | 85% |
| `application` | `features/*/application/` | 90% |
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

No se comprueban timestamps exactos: los eventos solo deben ser finitos.

## E2E

`tests/e2e/test_monitor_e2e.py` usa la misma muestra, carga `zones.json` real desde
el composition root (`main.build_monitor_pipeline`) y levanta un
`ThreadingHTTPServer` en `127.0.0.1:0`. Valida `/`, `/api/state`, `/api/frame` y
`/api/frame?after=35`: estado `running`, 35 frames, eventos y contadores,
persona con zona y etiqueta, JPEG con cabecera de secuencia y métricas
(`fps`, `processing_ms`, `dropped_frames`, `age_seconds`) coherentes. El detector,
ReID y extractor son fakes; el video es archivo local.

`develop` aún no incluye los endpoints `/api/health` y `/api/metrics` de ECM-75;
cuando se integren, este e2e debe ampliarse para consultarlos.

## CI y artefactos

- `ci.yml`: instala dependencias, ejecuta unit + integración con cobertura,
  verifica umbrales globales y por módulo, y sube `coverage-pr` (XML, JSON y HTML)
  siempre. En fallo sube `pytest-pr-logs`.
- `e2e.yml`: `schedule` diario y `workflow_dispatch` manual. Ejecuta solo `-m slow`
  y sube `pytest-e2e-logs` siempre.
- El job `build` solo compila; `lint.yml` mantiene Ruff y formato.

Las pruebas reales optativas con cámara, modelos pesados o CUDA siguen fuera de
estos jobs y se documentan en [validation.md](validation.md).
