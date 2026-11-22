# Type checking con mypy

Este documento describe el chequeo estático de tipos, sus límites actuales y la
forma de resolver errores sin ocultarlos.

## Decisión

Se usa **mypy 1.11.2** con Python objetivo **3.10** (la CI ejecuta el chequeo con
Python 3.11). Se eligió mypy por ser una herramienta Python pura, sin runtime de
Node, y por integrarse con `pyproject.toml` y variables de entorno.

Los chequeos son **graduales**: mypy analiza `src/` y `main.py`, incluidos los
scripts de `src/vision_core/scripts/` y el kernel de `src/vision_core/core/`;
no se activa `strict` ni se exige anotar todas las funciones. Los contratos
compartidos de `core/dto/` y `core/serialization/` se comprueban con el mismo
perfil que el resto de `src/`.

## Ejecutar localmente

Instala las dependencias de desarrollo en el mismo entorno virtual del proyecto:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m mypy
```

`mypy` lee la configuración de `[tool.mypy]` en `pyproject.toml`. El workflow
[CI Tests](../.github/workflows/ci.yml) ejecuta el job **Type Check** de forma
separada del job de Ruff y de la suite de pytest.

## Alcance y fases de adopción

| Fase | Alcance | Estado |
|---|---|---|
| Actual | `src/` y `main.py`, con `check_untyped_defs` | Activa |
| Siguiente | Añadir `tests/` al alcance y corregir sus anotaciones | Pendiente |
| Futura | Stubs/plugins de terceros y flags más estrictos | Pendiente |

El directorio `scripts/` de la raíz no contiene archivos Python versionados. Los
scripts reales viven en `src/vision_core/scripts` y ya quedan cubiertos por
`files = ["src", "main.py"]`.

`ignore_missing_imports = true` permite analizar el código propio aunque
OpenCV, Torch, Ultralytics u otra dependencia no publique stubs. No sustituye al
tipado de esos límites: al añadir nuevas integraciones, prefiere adaptadores con
protocolos propios en `domain/` y revisa que los tipos no se degraden a `Any`.
PyYAML sí publica stubs; se instalan desde `requirements-dev.txt` y se usan al
verificar `config/models.yml` y su loader.

## Interpretar errores

- `union-attr`, `index` o `operator`: normalmente falta comprobar `None` o un
  valor opcional. Resuelve con un guard o una validación explícita.
- `attr-defined`: el receptor no declara el atributo. Evita `getattr` como
  solución por defecto; define un protocolo o un `cast` acotado con
  `TYPE_CHECKING` cuando el contrato real lo garantice.
- `arg-type`, `assignment` o `return-value`: ajusta el tipo del valor o valida y
  convierte en la frontera (por ejemplo, datos de JSON o configuración).
- `var-annotated`: anota los contenedores vacíos (`list[str]`, `dict[str, int]`,
  `deque[dict[str, object]]`).
- `call-overload`: revisa la firma real de la librería; no fuerces un `cast` sin
  comprobar el contrato.

Cada error incluye un código entre corchetes; úsalo para buscar el caso concreto
en la documentación de mypy. Corrige la causa antes de plantear una excepción.

## Convenciones

- No introducir `Any` nuevos sin justificar el límite en el código o en este
  documento.
- No usar `# type: ignore` sin código de error y motivo:
  `# type: ignore[código]  # motivo`. Un `ignore` sin código o que oculte un
  error corregible no se acepta.
- Los `cast` deben estar respaldados por una garantía comprobable (contrato de
  una librería, validación previa o protocolo). No se usan para silenciar un
  error de diseño.
- No se añaden excepciones por archivo para evitar errores; si una excepción es
  imprescindible, se registra aquí con justificación y fecha de revisión.

## Excepciones documentadas

| Archivo/módulo | Excepción | Motivo | Revisión |
|---|---|---|---|
| Terceros (`cv2`, `torch`, `ultralytics`, etc.) | `ignore_missing_imports` global | Paquetes sin stubs completos | Al adoptar stubs o plugins |
| Tests | Excluidos de `files` | Fase siguiente de adopción | Al añadir `tests/` |

No hay `# type: ignore` en `src/` ni en `main.py` a la fecha de este documento.

## Verificar que el chequeo bloquea errores

Para comprobar la configuración, introduce temporalmente un error evidente en
código cubierto (por ejemplo, un retorno incompatible en un adaptador de
`infrastructure/`) y ejecuta mypy:

```python
# Error temporal, no commitear
valor: int = "texto"
```

```bash
python -m mypy
```

El comando debe fallar con un código como `assignment` en el archivo modificado.
Revierte el cambio y confirma que `python -m mypy` vuelve a terminar con
`Success: no issues found`. Este chequeo no reemplaza `pytest`, Ruff ni
`compileall`; cada uno cubre una parte distinta de la calidad.
