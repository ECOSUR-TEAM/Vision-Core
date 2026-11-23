# ADR 0011: Editor de zonas del monitor con contrato versionado y auditoría

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-23 |
| Tipo | Arquitectura |
| Prioridad | Media |
| Ticket | ECM-103 |
| Etiquetas | `adr`, `monitor`, `zonas`, `http`, `auditoria` |
| Dependencias | ADR 0001; ADR 0004; ADR 0008; ADR 0009 |
| Impacto | Nuevo slice `zone_editor`, rutas `/api/v1/zones*`, configuración de token y auditoría; el pipeline existente no se recarga en caliente. |

## Contexto

El monitor ya dibuja zonas configuradas en `config/zones.json`, pero ajustar los
polígonos obliga a editar YAML/JSON a mano, reiniciar y validar por separado. La
interfaz debe permitir arrastrar vértices, validar con el mismo esquema que usa
el pipeline y guardar sin romper el archivo ni perder trazabilidad. El editor se
ofrece antes de que exista autenticación completa (tickets 42/50), por lo que
necesita una barrera explícita y no puede confundirse con control de acceso.

## Decisión

- Mantener la edición en `features/monitor/infrastructure/zone_editor` con
  `config`, `access`, `storage`, `audit` y `service`; los DTO y la validación
  siguen viniendo de `core/validation/zone_payload.py`.
- Exponer `GET /api/v1/zones`, `PUT /api/v1/zones` y
  `POST /api/v1/zones/validate` bajo `/api/v1`, conservando las rutas sin
  prefijo como alias compatibles y marcadas como deprecadas en la respuesta.
- Activar el editor con `VISION_CORE_ZONE_EDITOR_ENABLED=1` o `--zone-editor`;
  ambas variantes exigen token y archivo de auditoría, y requieren un archivo
  real de zonas. Sin esos valores las rutas devuelven `404` y la UI oculta el
  editor.
- Autorizar sólo con `Authorization: Bearer <token>` comparado en bytes mediante
  `hmac.compare_digest`; `X-Vision-User` se sanea únicamente como etiqueta de
  auditoría. Los nombres de cabecera se normalizan a minúsculas en el handler.
- Escribir con archivo temporal, `fsync`, `os.replace`, preservando permisos y
  restaurando el contenido previo si falla la escritura o la auditoría. Cada
  guardado añade una línea JSONL inmutable con hashes anterior y nuevo.
- Serializar guardados concurrentes con un `RLock` por servicio y devolver
  `restart_required: true`: las zonas ya cargadas en el pipeline no se recargan
  porque eso alteraría el análisis en curso.

## Consecuencias

### Positivas

- Un único esquema valida la UI, la API y el pipeline; no hay deriva de formatos.
- El archivo de zonas queda siempre en estado válido y auditable.
- El contrato es explícito sobre reinicio y límites de payload.

### Negativas y costes

- El token es una barrera temporal, no autenticación de usuario; habrá que
  sustituirlo al llegar los tickets 42/50.
- Requiere variables de entorno adicionales y un directorio de auditoría con
  permisos controlados.
- Guardar zonas no surte efecto en el proceso en ejecución.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Cabeceras en minúsculas del navegador rechazadas por el gate | Normalización a minúsculas en handler y `access.py`. |
| Cuerpo sobredimensionado leído antes de validarse | Tope configurado aplicado también a la lectura cruda del archivo. |
| Pérdida de permisos o backup parcial | Preservación de `stat.S_IMODE`, `fsync` y restauración atómica. |
| Cadena de auditoría rota por guardas simultáneas | `RLock` en `ZoneEditorService.save`. |
| Log de éxito aunque falle la auditoría | El log `zone_editor_audit` se emite después de escribir el JSONL. |
| Cambio no aplicado hasta reiniciar | `restart_required: true` y aviso en la UI y la documentación. |
