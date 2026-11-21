# Property-based y fuzz tests de zonas y geometría

Los tests viven en `tests/features/door/` y usan generadores deterministas de
`tests/fakes/geometry_generators.py` con semilla fija `20240517`.

## Decisión sobre `hypothesis`

`hypothesis` no está instalado ni aprobado como dependencia de desarrollo. Para
no agregar dependencias pesadas ni ejecución larga en CI se usan generadores
propios con `random.Random(seed)`, revisión explícita de la semilla y un número
acotado de ejemplos (200 puntos por invariante).

## Invariantes cubiertos

- `PolygonDoorAnalytics._point_in_polygon` es determinista y no lanza excepción
  para puntos finitos, incluidos valores extremos.
- Un punto en el centro de un rectángulo válido permanece dentro tras
  perturbaciones controladas del orden de `1e-6`.
- `validate_polygon` rechaza polígonos con menos de 3 vértices, vértices
  repetidos, `NaN` e `Infinity`.
- `PolygonDoorAnalytics` no emite evento antes de `confirmation_frames` frames
  estables, y descarta transiciones inestables que no alcanzan el umbral.
- `load_zones` rechaza JSON truncado con `ZoneConfigurationError` y mensaje
  estable `JSON malformado en ...`; también rechaza claves duplicadas,
  coordenadas no finitas y más de 100 puntos por zona.
- Los generadores producen secuencias idénticas para la misma semilla.

## Reproducibilidad

Cada generador crea su propio `random.Random(seed)`, por lo que el orden de los
tests no afecta los resultados. Los archivos temporales se crean con `tmp_path`;
ningún test usa cámara, red, modelos, archivos externos ni tiempo real.

## Resultados

Los ejemplos generados no revelaron bugs nuevos en la validación de zonas ni en
la geometría; no hay tickets hijos pendientes por este trabajo. Si aparece un
fallo, se debe reducir a un ejemplo mínimo con su semilla y registrar un ticket
separado antes de cambiar la semántica de eventos.
