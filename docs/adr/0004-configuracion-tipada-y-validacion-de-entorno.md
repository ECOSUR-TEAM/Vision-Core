# ADR 0004: Configuración tipada y validación de entorno

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-20 |
| Tipo | Configuración / Decisión |
| Prioridad | Media |
| Ticket | ECM-84 (documenta la decisión de ECM-74) |
| Etiquetas | `adr`, `settings`, `configuration`, `validation`, `env` |
| Dependencias | ADR 0001; configuración centralizada (ECM-74) |
| Impacto | Toda ejecución local, Compose y CI |

## Contexto

Las variables de entorno se leían con `os.getenv` repartido entre adaptadores.
Eso dificultaba saber qué valor estaba activo, producía errores en tiempo de
ejecución y permitía valores imposibles (booleanos arbitrarios, URLs RTSP
incompletas, puertos fuera de rango). Además, Python no carga `.env` por sí
solo, mientras Compose sí lo hace mediante `env_file`, lo que generaba
diferencias entre entornos.

## Decisión

Centralizar la configuración en `vision_core.core.config`:

- `Settings` es un `dataclass(frozen=True, slots=True)` con ocho secciones:
  `video`, `detection`, `reid`, `zones`, `monitor`, `logging`, `performance` y
  `camera` (`src/vision_core/core/config/settings_config.py`).
- `Settings.from_env()` convierte y valida todos los valores antes de construir
  adaptadores. Acumula los errores y termina con `SettingsError` indicando la
  variable exacta y una acción correctiva, en lugar de fallar más adelante.
- Los booleanos se normalizan en `core/config/settings_helpers.py` (`1/0`, `true/false`,
  `yes/no`, `on/off`); las URL RTSP exigen esquema, host y puerto válido;
  `redact_sensitive()` oculta credenciales antes de registrar o informar URLs.
- La configuración de persistencia es `PersistenceSettings` y la del pipeline
  es `PipelineConfig`; ambas se leen desde el entorno y se inyectan desde
  `main.py`. No se crea un objeto global mutable.
- `.env.example` es la lista canónica de variables y `docs/configuration.md`
  su catálogo. Docker Compose carga `.env` por `env_file`; en ejecución Python
  hay que exportarlo (`set -a; source .env; set +a`).
- El composition root es el único lugar que decide qué configuración llega a
  cada feature. Los módulos de dominio no leen el entorno.

## Consecuencias

### Positivas

- Fallo rápido y mensajes accionables antes de abrir video o cargar modelos.
- Un único sitio para añadir una variable, con su validación y su documento.
- Menos riesgo de exponer credenciales en logs al redactar las URLs.

### Negativas y costes

- Añadir una variable exige tocar settings, `.env.example`, documentación y
  pruebas.
- Los puntos de entrada heredados usan `validate_startup=False` para no exigir
  archivos propios de despliegues completos; esa excepción debe documentarse.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La documentación se desalinea del código | El PR que añade una variable actualiza `.env.example` y `docs/configuration.md`. |
| Un valor inválido aparece solo en producción | Validación en `from_env()` y prueba de arranque en entorno limpio del onboarding. |
| Credenciales en logs o incidencias | `redact_sensitive()` y la regla de no pegar URLs RTSP en reportes. |

## Alternativas consideradas

1. **Leer `os.getenv` en cada adaptador.** Descartada: validación dispersa y
   errores tardíos.
2. **Cargar `.env` automáticamente en Python.** Descartada: oculta la diferencia
   entre ejecución local y Compose y añade una dependencia.
3. **Un modelo de configuración con validación externa (por ejemplo Pydantic).**
   Descartada por ahora: la validación actual basta y no justifica otra
   dependencia.

## Verificación

```bash
make setup
python -m pip install -r requirements-dev.txt
make run
python -m pytest -q
python -m mypy
ruff check .
```

Comprobación manual: copiar `.env.example`, dejar una variable inválida y
confirmar que `python main.py` termina con `SettingsError` antes de abrir el
stream. El catálogo vigente está en [configuración tipada](../configuration.md).

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| - | - | - | - |
