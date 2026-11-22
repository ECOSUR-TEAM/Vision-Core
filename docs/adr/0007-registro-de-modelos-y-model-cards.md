# ADR 0007: Registro de modelos y model cards

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-21 |
| Tipo | MLOps / Gobernanza |
| Prioridad | Media |
| Ticket | ECM-99 |
| Etiquetas | `mlops`, `model-registry`, `model-card`, `provenance`, `reproducibility` |
| Dependencias | Tickets 33, 36, 37, 42 y 56 |
| Impacto | Reproducibilidad, auditoría de licencias y rollback de modelos |

## Contexto

El detector y el extractor de embeddings se configuran hoy solo por variables de entorno.
El código conoce rutas o nombres (`yolov8n.pt`, `mobilenet_v3_small`, `resnet50`), pero no
registra versión del artefacto, procedencia verificable, licencia, checksum ni
configuración esperada. Eso impide reproducir resultados, auditar licencias y hacer
rollback de un cambio de modelo.

Los pesos no son código y están excluidos por `.gitignore` (`*.pt`, `*.pth`). Las
mediciones disponibles son sintéticas y no separan la precisión por modelo.

## Decisión

Mantener un registro ligero en texto en `config/models.yml`, validado por un loader
estricto en `vision_core.model_registry`. Cada entrada define un `id` estable, nombre,
versión, `artifact_version`, selector, proveniencia, licencia, fecha de registro,
checksum opcional, configuración esperada y ruta a una model card.

La resolución `resolve_active_models()` ocurre en el composition root antes de abrir el
stream. Valida ID, tarea, estado, selector y configuración esperada. El checksum del
detector se verifica contra `VISION_CORE_MODEL_PATH` cuando el registro declara un valor:
si el archivo falta o no coincide, el arranque falla. Los pesos de embedding gestionados
por torchvision declaran `null` porque no exponen una ruta local verificable; en ese caso
`model_hash` es `unverified`. Los descriptores se inyectan en los adaptadores de detección
y ReID; la identidad se publica en logs JSON y en `/ready` de forma aditiva. `/health`
permanece como liveness sin metadata.

Las model cards viven en `docs/model-cards/`, con una plantilla común. Los datos no
verificados se marcan `UNKNOWN` o `unpinned`; nunca se inventan hashes ni licencias.

## Consecuencias

### Positivas

- El arranque falla tempranamente con `ConfigurationError` si el `model_id` no existe,
  está inactivo, su selector/configuración difiere o el checksum declarado no coincide.
- `model_id`, `model_version` y `model_hash` aparecen en logs y `/ready`, con el prefijo
  `embedding_` para la variante de ReID.
- Adoptar una versión exige añadir una entrada y una model card; hacer rollback exige
  conservar la entrada anterior como `deprecated`.

### Negativas y costes

- El selector del detector queda acoplado al nombre base de `VISION_CORE_MODEL_PATH`;
  nombres propios como `best.pt` exigen actualizar el registro.
- Los modelos de embedding no pueden verificar checksum local; su hash se reporta
  `unverified` hasta que exista un mecanismo de artefactos versionados.
- No se suben binarios, no se descarga nada en CI y no se crea un servidor de modelos.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Cambio de pesos sin cambio de `model_id` | Checksum SHA-256 declarado y verificación fail-closed para el detector. |
| Licencia desconocida o mal interpretada | Campos `license`, `license_url` y `license_notes` en cada model card; `UNKNOWN` cuando no hay evidencia. |
| Arranque roto por configuración incompatible | Validación temprana con mensaje accionable y rollback a la entrada `deprecated`. |

## Alternativas consideradas

- Registro en base de datos: descartado; el equipo quiere texto versionado y no hay un
  servicio de persistencia disponible en el arranque.
- Servidor de modelos o feature store: fuera de alcance del ticket.
- Derivar la identidad solo del nombre de archivo: insuficiente para auditabilidad y
  rollback.
- Inventar hashes a partir de la versión del paquete: descartado; la versión de la
  biblioteca no identifica el artefacto.

## Verificación

- `config/models.yml` contiene los tres modelos usados por el pipeline.
- Cada modelo tiene model card con métricas, licencia, limitaciones y rollback.
- Los tests cubren carga estricta, ID desconocido, selector inválido, checksum y
  consistencia entre entorno y registro.
- Los tests del registro pasan junto con `ruff` y `mypy`; `/health` conserva su contrato.

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| - | - | - | - |
