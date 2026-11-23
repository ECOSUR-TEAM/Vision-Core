# Registro de modelos y model cards

Vision Core declara qué modelos puede usar en `config/models.yml`: un registro en texto,
versionado y validado al arranque. No contiene pesos, no descarga modelos en CI y no
sustituye a un servidor de modelos ni a un feature store.

## Identidad estable

Cada entrada usa estos campos:

| Campo | Uso |
|---|---|
| `id` | Identificador estable e inmutable del modelo (`detection.person.yolov8n`). |
| `name` | Nombre corto de la familia. |
| `task` | `detection` o `embedding`. |
| `version` | Versión de la entrada/registro; se expone como `model_version`. |
| `artifact_version` | Revisión conocida del artefacto; `unpinned` cuando no está fijada. |
| `selector` | Valor que debe coincidir con la configuración (`yolov8n.pt`, `mobilenet_v3_small`). |
| `source` / `source_url` | Proveniencia declarada, sin credenciales. |
| `license` / `license_url` / `license_notes` | Licencia declarada y salvedades. |
| `registered_at` | Fecha ISO 8601 de alta en el registro; no fecha de entrenamiento. |
| `checksum.algorithm` / `checksum.value` | Algoritmo y hash/checksum SHA-256; `null` significa no verificado. |
| `expected_config` | Configuración esperada que debe coincidir con el entorno; `precision` es opcional y por defecto `fp32`. |
| `model_card` | Ruta a la ficha del modelo. |
| `status` | `active`, `deprecated` o `experimental`; solo `active` se resuelve en arranques normales. |

`model_hash` en logs y `/ready` es `sha256:<hex>` solo cuando `VISION_CORE_MODEL_CHECKSUM_VERIFY=1`,
el registro declara checksum y el archivo local se verificó. En cualquier otro caso es
`unverified`. Un checksum ausente es explícito y auditable; nunca se inventa.

## Validación al arranque

`resolve_active_models()` se ejecuta antes de abrir el stream y comprueba:

1. `VISION_CORE_MODEL_REGISTRY_FILE` existe y usa `schema_version: "1.0"`.
2. `VISION_CORE_DETECTION_MODEL_ID` y `VISION_CORE_EMBEDDING_MODEL_ID` existen, están
   activos y corresponden a la tarea solicitada.
3. El `selector` coincide con `VISION_CORE_MODEL_PATH` y `VISION_CORE_EMBEDDING_MODEL`.
4. La configuración esperada coincide con confianza, clases, perfil de pesos y precisión.
   Las variantes INT8 y FP16 son entradas distintas: cambio de `id`, `selector` y
   `expected_config.precision`; la familia (`name`) se conserva para rollback.
5. Si el registro declara checksum, el SHA-256 calculado coincide. Si el archivo local
   falta o no coincide, el arranque falla; sin checksum declarado, el hash queda
   `unverified`.

Un `model_id` desconocido, un selector distinto, un checksum declarado sin archivo local
o una discrepancia de checksum terminan el arranque con `ConfigurationError`
(`CONFIGURATION_INVALID`) y un mensaje accionable. Los pesos de embedding gestionados por
torchvision no tienen ruta local verificable y declaran `null`.

## Adoptar una nueva versión

1. Obtén los pesos por el canal declarado en `source`; **no los subas al repositorio**.
2. Calcula el checksum: `sha256sum yolov8n-v2.pt` (o el comando equivalente de tu SO).
3. Copia `docs/model-cards/TEMPLATE.md` a `docs/model-cards/<modelo>.md` y completa
   métricas, licencia, proveniencia, limitaciones y rollback.
4. Añade una entrada nueva en `config/models.yml` con `version` nuevo. Conserva la
   entrada anterior con `status: deprecated` para permitir rollback. Si comparas
   variantes INT8/FP32 del mismo modelo base (ticket 56), mantené el mismo `name` y
   usa `id`, `version` y `selector` distintos.
5. Valida: `python -m pytest tests/test_model_registry.py -q`.
6. Cambia `VISION_CORE_DETECTION_MODEL_ID` / `VISION_CORE_EMBEDDING_MODEL_ID` (y la ruta
   o el nombre cuando corresponda), reinicia y comprueba `model_id`, `model_version` y
   `model_hash` en logs y `/ready`.

## Volver a la versión anterior

1. Restaura el artefacto de la versión previa: `VISION_CORE_MODEL_PATH` para detección o
   la caché de torchvision para embedding.
2. Asigna a `VISION_CORE_DETECTION_MODEL_ID` o `VISION_CORE_EMBEDDING_MODEL_ID` el ID
   de la entrada `deprecated` que se conservó en el registro.
3. Reinicia; `/ready` debe mostrar el ID y la versión anteriores. Si el checksum está
   fijado, el arranque fallará cuando los pesos restaurados no coincidan.
4. Registra el motivo del rollback en el changelog de la versión y en la model card.

## Verificación

```bash
python -m pytest tests/test_model_registry.py -q
python -c "from vision_core.core.config import Settings; from vision_core.model_registry.activation import resolve_active_models; print(resolve_active_models(Settings.from_env({'VISION_CORE_RTSP_URL':'rtsp://localhost:8554/x'}, validate_startup=False)).as_log_identity())"
curl http://127.0.0.1:8080/ready
```

`vision_core.model_registry` sigue siendo el path transitorio permitido por ADR 0007;
su migración a `core/model_registry/` está diferida al ticket 67 (ADR 0008).

Para simular una alerta de checksum, cambia temporalmente `checksum.value` en una copia
del registro y apunta `VISION_CORE_MODEL_REGISTRY_FILE` a esa copia con un archivo local
presente. El arranque debe fallar antes de cargar el pipeline.

## Fuera de alcance

- Descargar modelos automáticamente en CI.
- Servir modelos remotamente o implementar un feature store.
- Reentrenar modelos o subir pesos al repositorio.
