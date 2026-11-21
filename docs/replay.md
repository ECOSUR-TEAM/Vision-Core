# Replay determinista con goldens

Este runner reproduce el pipeline sin cámara, red, modelos ni descargas. Inyecta
detecciones grabadas en JSON y compara los eventos emitidos contra archivos
golden legibles.

## Entradas

Los clips golden viven en `tests/regression/fixtures/` como detecciones por
frame, no como video. Cada escenario versiona:

- `name`, `seed` (semilla documentada, actualmente `1337`),
- `resolution` y `fps`,
- `zones` (archivo de zonas versionado),
- `detector` (origen de las detecciones, sin modelo real),
- `frames` (una detección por frame con `x`, `y`, `track_id` y `confidence`).

Escenarios base (suite por defecto):

- `enter_exterior_to_interior`
- `exit_interior_to_exterior`
- `false_alarm`
- `person_stopped`

Escenario extendido (marcado `replay_extended`, se ejecuta en el job opcional,
o con `pytest -m replay_extended`): `lighting_change`.

## Comparación

Se comparan `event`, `person_id`, metadata y el orden de eventos con un diff
unificado. El `timestamp` se normaliza a tiempo relativo al frame (`frame/fps`)
y se tolera una desviación de `TIMING_TOLERANCE_SECONDS` (0.25 s, un frame a
10 fps). Cualquier otro cambio rompe el test.

## Regeneración

Solo con el flag explícito:

```bash
python -m pytest tests/regression --regen-golden -q
```

La regeneración debe revisarse y aprobarse en el PR del cambio que la motiva;
el golden se actualiza únicamente cuando el cambio de eventos es intencional.
El diff del PR es la evidencia de aprobación.
