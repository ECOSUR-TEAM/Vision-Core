# Decisiones de arquitectura (ADR)

Este directorio registra las decisiones de arquitectura de Vision Core. Cada
ADR es un archivo Markdown autónomo con contexto, decisión, consecuencias,
alternativas y verificación.

| ADR | Título | Estado | Fecha |
|---|---|---|---|
| [0001](0001-screaming-architecture-vertical-slice.md) | Screaming Architecture + Vertical Slice con capas por feature y DTOs | Aceptada | 2026-11-17 |
| [0002](0002-persistence-and-retention.md) | Persistencia y retención de eventos, tracks e historial | Aceptada | 2026-11-19 |
| [0003](0003-modelo-ejecucion-multi-camara.md) | Modelo de ejecución multi-cámara y estrategia de ReID compartido | Propuesta | 2026-11-19 |

Convención: `NNNN-titulo-en-kebab.md`, un H1 por documento y tabla de metadatos
(estado, fecha, tipo, ticket, dependencias). Las decisiones no se modifican: si
cambian, se registra un ADR nuevo que sustituye al anterior.
