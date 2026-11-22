# Pipeline slice

`application/` holds `RunPipeline`, its DTOs, mappers and the factory used by the
composition root. It orchestrates video, detection, ReID, door analytics and
monitor callbacks without owning domain entities of those features.
`infrastructure/` contains only adapters needed to construct the runner.

Keep the feature boundaries: the pipeline imports public contracts from other
slices, never their infrastructure.

## Documentation

- [Pipeline data flow (Mermaid)](../../../../docs/diagrams.md#flujo-de-datos)
- [Component diagram](../../../../docs/diagrams.md#c4--componentes)
- [Architecture and import rules](../../../../docs/architecture.md)
- [ADR 0001](../../../../docs/adr/0001-screaming-architecture-vertical-slice.md)
- [Runbook: no events generated](../../../../docs/runbooks/06-no-se-generan-eventos.md)
