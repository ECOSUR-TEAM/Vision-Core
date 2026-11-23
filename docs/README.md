# Documentación de Vision Core

Índice único de la documentación viva. El [README](../README.md) es la entrada
rápida; aquí está el mapa completo. Todo documento debe ser breve, accionable y
apuntar al código o a la operación real. Si encuentras un comando que ya no
existe, corrígelo en el mismo PR que lo detecta.

## Empieza aquí

| Documento | Para qué sirve |
|---|---|
| [Onboarding](onboarding.md) | Instalar, arrancar y dar los primeros pasos |
| [Glosario](glossary.md) | Qué significan track, evento, zona, `person_id`, etc. |
| [Diagramas (Mermaid)](diagrams.md) | Contexto C4, contenedores, componentes y flujo de datos |
| [Arquitectura](architecture.md) | Vertical slices, capas, reglas de imports y DTOs |
| [Desarrollo local](development.md) | Comandos `make`, Dev Container y troubleshooting |
| [Proceso de contribución](../CONTRIBUTING.md) | Ramas, commits, PR, CODEOWNERS, SLA y DoD |

## Decisiones

| Documento | Para qué sirve |
|---|---|
| [Índice de ADR](adr/README.md) | Todas las decisiones de arquitectura, su estado y sus enmiendas |
| [ADR 0007: registro de modelos](adr/0007-registro-de-modelos-y-model-cards.md) | Identidad, checksum y trazabilidad de modelos |
| [ADR 0008: capa core](adr/0008-core-layer-and-dependency-rules.md) | Contrato de dependencias entre `features/`, `core/` y `scripts/` |
| [Plantilla de ADR](adr/_template.md) | Cómo registrar una decisión nueva |

## Operación

| Documento | Para qué sirve |
|---|---|
| [Runbooks](runbooks/README.md) | Ante un incidente: síntoma, verificación y acción |
| [Arranque y parada](startup.md) | Stack por defecto y perfil `camera` |
| [Requisitos y problemas conocidos](operations.md) | Límites funcionales y diagnóstico |
| [Configuración tipada](configuration.md) | Variables, defaults y validación |
| [Observabilidad](observability.md) | `/health`, `/ready`, `/metrics`, logs y métricas |
| [Calidad de cámara](camera-quality.md) | Señales de calidad, deriva, umbrales y acciones |
| [Persistencia y retención](persistence.md) | SQLite, TTLs, backup y degradación |
| [Monitor](monitor.md) | Interfaz web, API y render |
| [Exposición del monitor y binding](monitor-exposure.md) | Binding seguro, advertencias y verificación de puertos |
| [Cámara Ethernet](ethernet-camera.md) | Evidencia y diagnóstico de la cámara FD8134 |
| [Frigate](frigate.md) | Integración local con webcam y go2rtc |
| [Catálogo de errores](errors.md) | Códigos estables y jerarquía |
| [Contratos versionados](api-contracts.md) | API `v1` y esquema de eventos |
| [Releases](releases.md) | Versionado, tags, publicación y rollback |
| [Registro de modelos](model-registry.md) | Alta, adopción y rollback de modelos |
| [Seguridad y supply chain](security.md) | Escaneos, dependencias y permisos |
| [Revisión legal](legal-review.md) | Inventario AGPL, bloqueos legales y aprobación pendiente |
| [Privacidad y retención](privacy-retention.md) | Bases legales, minimización, retención y derechos |

## Calidad y evidencia

| Documento | Para qué sirve |
|---|---|
| [Pruebas](testing.md) | Niveles, cobertura y comandos |
| [Validación](validation.md) | Stream, zonas, eventos y evaluación |
| [Type checking](type-checking.md) | mypy, convenciones y excepciones |
| [Contratos DTO](dto-contracts.md) | Snapshots, reconstrucción y compatibilidad entre capas |
| [Property testing](property-testing.md) | Geometría de zonas, invariantes y fuzz determinista |
| [Replay determinista](replay.md) | Golden videos, fixtures y comparación de eventos |
| [Presupuestos de rendimiento](performance.md) | Baselines, hotspots, smoke y benchmark nocturno |
| [Matriz edge / INT8](benchmark-edge.md) | Perfiles FP32/INT8/FP16, calidad antes que FPS y promoción |
| [Plan G0](g0-baseline-plan.md) | Instrumentación del pipeline de una cámara |
| [Model cards](model-cards/TEMPLATE.md) | Plantilla y fichas de procedencia, licencia y límites |
| [Evaluación de la sala](../reports/room-evaluation.md) | Resultados y pendientes reales |
| [Cámara Ethernet](../reports/ethernet-camera-evaluation.md) | Evidencia de la FD8134 |
| [Webcam con Frigate](../reports/webcam-frigate.md) | Prueba de integración local |

## Cómo mantenerla

1. Un cambio de comportamiento se entrega con su documentación en el mismo PR;
   forma parte del [Definition of Done](development.md#definition-of-done).
2. La arquitectura se documenta con un ADR nuevo o una enmienda fechada; no se
   reescribe la historia. Consulta [el índice de ADR](adr/README.md).
3. Los diagramas se editan como texto Mermaid en [diagrams.md](diagrams.md).
4. Antes de mergear, abre los enlaces del PR y ejecuta los comandos que citas.
   Un enlace roto o un comando obsoleto se corrige antes del merge.

## Revisión

La aceptación exige revisión por alguien distinto del autor. No se marca como
hecha hasta que esa persona la confirme.

| Entrega | Autor | Revisor | Estado |
|---|---|---|---|
| ECM-84: ADR 0004-0006, diagramas, runbooks, onboarding y glosario | Autor del PR ECM-84 | @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-85: proceso de PR, CODEOWNERS y DoD | @MelissaZarate08 | @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-99: registro de modelos y model cards | @MelissaZarate08 | @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-105: ADR 0008 y contrato de capas | @bchanona | @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-106: migración de `shared/` a `core/` | @bchanona | @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-107: migración de settings y application a core config y core telemetry | @MelissaZarate08 | @Carlosss2, @FabricioPRZ, @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-108: consolidación de domain en core domain y core contracts | @MelissaZarate08 | @Carlosss2, @FabricioPRZ, @Ameth-Toledo | [x] Revisado por otra persona |
| ECM-111: eliminación de los paquetes legacy y documentación viva | @bchanona | @Carlosss2 | [x] Revisado por otra persona |
| ECM-87: licencias, privacidad y retención de video | @bchanona | @Ameth-Toledo, @Carlosss2 | Pendiente de revisión |
| ECM-95: binding seguro y exposición del monitor | @bchanona | @Ameth-Toledo, @Carlosss2 | [x] Revisado por otra persona |
| ECM-101: matriz edge INT8/FP16 con presupuestos | @MelissaZarate08 | @Ameth-Toledo, @Carlosss2 | Pendiente de revisión |
| ECM-100: calidad de cámara y deriva de calibración | @MelissaZarate08 | @Ameth-Toledo, @bchanona, @Carlosss2, @FabricioPRZ | Pendiente de revisión |
| ECM-109: persistencia en core y serialización de eventos | @bchanona | @Ameth-Toledo, @Carlosss2 | Pendiente de revisión |
