# Arquitectura y límites de imports

Vision Core usa Vertical Slice: cada feature es dueño de sus casos de uso,
dominio y adaptadores. `shared/` contiene únicamente tipos estables y
transversales; no debe convertirse en un segundo dominio global.

## Estructura de tests

Los tests espejo viven bajo `tests/features/<feature>/{application,domain,infrastructure}`.
Los tests transversales están en `tests/integration/`, `tests/evaluation/` y
`tests/shared/`; los dobles reutilizables están en `tests/fakes/`.

## Reglas automáticas

`tests/architecture/test_import_rules.py` verifica que:

- `shared/` no importe features ni infraestructura.
- El dominio de un feature no importe `application` ni `infrastructure`.
- `application/` no importe `infrastructure`.
- Un feature no importe la infraestructura de otro feature.
- Los DTOs no dependan del dominio, infraestructura ni frameworks de visión.
- Solo los composition roots `main.py` y `composition.py` puedan importar
  factories de múltiples features.

`tests/architecture/test_one_class_per_file.py` mantiene la política de una
clase de nivel superior por archivo.

Estos checks se ejecutan junto con toda la suite mediante `python -m pytest` en
cada pull request. Si un check falla, mueve la dependencia al límite correcto
(normalmente un port o un mapper) en lugar de relajar la regla.

La decisión arquitectónica y sus motivaciones están registradas en
[ADR-0001](adr/0001-screaming-architecture-vertical-slice.md).
