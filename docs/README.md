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

## Decisiones

| Documento | Para qué sirve |
|---|---|
| [Índice de ADR](adr/README.md) | Todas las decisiones de arquitectura, su estado y sus enmiendas |
| [Plantilla de ADR](adr/_template.md) | Cómo registrar una decisión nueva |

## Operación

| Documento | Para qué sirve |
|---|---|
| [Runbooks](runbooks/README.md) | Ante un incidente: síntoma, verificación y acción |
| [Arranque y parada](startup.md) | Stack por defecto y perfil `camera` |
| [Requisitos y problemas conocidos](operations.md) | Límites funcionales y diagnóstico |
| [Configuración tipada](configuration.md) | Variables, defaults y validación |
| [Observabilidad](observability.md) | `/health`, `/ready`, `/metrics`, logs y métricas |
| [Persistencia y retención](persistence.md) | SQLite, TTLs, backup y degradación |
| [Monitor](monitor.md) | Interfaz web, API y render |
| [Catálogo de errores](errors.md) | Códigos estables y jerarquía |
| [Contratos versionados](api-contracts.md) | API `v1` y esquema de eventos |
| [Releases](releases.md) | Versionado, tags, publicación y rollback |
| [Seguridad y supply chain](security.md) | Escaneos, dependencias y permisos |

## Calidad y evidencia

| Documento | Para qué sirve |
|---|---|
| [Pruebas](testing.md) | Niveles, cobertura y comandos |
| [Validación](validation.md) | Stream, zonas, eventos y evaluación |
| [Type checking](type-checking.md) | mypy, convenciones y excepciones |
| [Evaluación de la sala](../reports/room-evaluation.md) | Resultados y pendientes reales |
| [Cámara Ethernet](../reports/ethernet-camera-evaluation.md) | Evidencia de la FD8134 |
| [Webcam con Frigate](../reports/webcam-frigate.md) | Prueba de integración local |

## Cómo mantenerla

1. Un cambio de comportamiento se entrega con su documentación en el mismo PR;
   forma parte del [Definition of Done (ticket 40)](development.md#definition-of-done-ticket-40).
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
| ECM-84: ADR 0004-0006, diagramas, runbooks, onboarding y glosario | Autor del PR ECM-84 | Pendiente de asignar | [ ] Revisado por otra persona |
