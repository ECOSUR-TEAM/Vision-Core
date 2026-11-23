# Decisiones de arquitectura (ADR)

Este directorio registra las decisiones de arquitectura de Vision Core. Cada
ADR es un archivo Markdown autónomo con contexto, decisión, consecuencias,
alternativas y verificación. Para crear uno, copia la
[plantilla](_template.md).

| ADR | Título | Estado | Fecha |
|---|---|---|---|
| [0001](0001-screaming-architecture-vertical-slice.md) | Screaming Architecture + Vertical Slice con capas por feature y DTOs | Aceptada | 2026-11-17 |
| [0002](0002-persistence-and-retention.md) | Persistencia y retención de eventos, tracks e historial | Aceptada | 2026-11-19 |
| [0003](0003-modelo-ejecucion-multi-camara.md) | Modelo de ejecución multi-cámara y estrategia de ReID compartido | Propuesta | 2026-11-18 |
| [0004](0004-configuracion-tipada-y-validacion-de-entorno.md) | Configuración tipada y validación de entorno | Aceptada | 2026-11-20 |
| [0005](0005-observabilidad-y-contratos-versionados.md) | Observabilidad, errores y contratos versionados | Aceptada | 2026-11-20 |
| [0006](0006-versionado-y-releases.md) | Versionado semántico, releases y rollback | Aceptada | 2026-11-20 |
| [0007](0007-registro-de-modelos-y-model-cards.md) | Registro de modelos y model cards | Aceptada | 2026-11-21 |
| [0008](0008-core-layer-and-dependency-rules.md) | Capa `core` y reglas de dependencia entre `features/`, `core/` y `scripts/` | Aceptada | 2026-11-21 |
| [0009](0009-calidad-de-camara-no-intrusiva.md) | Calidad de cámara no intrusiva y deriva de calibración | Aceptada | 2026-11-22 |
| [0010](0010-sinks-de-eventos-y-entrega-idempotente.md) | Sinks de eventos con entrega idempotente y backpressure | Aceptada | 2026-11-23 |

El prerrequisito G0 se instrumenta sin autorizar multi-cámara; su plan operativo está
en [docs/g0-baseline-plan.md](../g0-baseline-plan.md).

Convención: `NNNN-titulo-en-kebab.md`, un H1 por documento y tabla de metadatos
(estado, fecha, tipo, ticket, dependencias). Una decisión aceptada no se
reescribe: se añade una **enmienda fechada** en el propio ADR o, si el cambio
es estructural, se marca como **Obsoleta** y se crea un ADR nuevo que la
sustituya. Mantén este índice actualizado en el mismo PR.
