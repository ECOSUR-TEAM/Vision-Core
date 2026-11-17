# ADR-001: organización por Vertical Slice

- **Estado:** aceptado
- **Decisión:** cada feature se organiza en `application`, `domain` e
  `infrastructure`; `shared` se limita a conceptos transversales estables.

Las dependencias apuntan hacia contratos y DTOs. La aplicación no conoce
adaptadores de infraestructura, y un feature no importa la infraestructura de
otro. Los límites ejecutables están documentados en
[architecture.md](../architecture.md) y cubiertos por
`tests/architecture/test_import_rules.py`.

La composición concreta de múltiples features ocurre únicamente en el
`main.py` raíz. La política de una clase por archivo se mantiene como una
restricción independiente para facilitar la navegación y el reemplazo de
adaptadores.
