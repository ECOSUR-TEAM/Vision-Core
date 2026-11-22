# Door slice

The door feature keeps zone-crossing behavior behind a domain port.

- `domain/` contains the analytics port and zone observations.
- `application/` exposes `UpdateZone` and `GetHistory` through immutable DTOs.
- `infrastructure/` contains polygon analytics, zone configuration, validation,
  loading, and dependency construction.
- Shared `Polygon` and `Event` types come from `vision_core.shared`.

The same three-layer structure is used by the detection pilot and should be
preserved by future vertical slices.

## Documentation

- [Zone and door calibration](../../../../docs/validation.md#calibrar-puerta-y-zonas-con-la-cámara)
- [Runbook: no events generated](../../../../docs/runbooks/06-no-se-generan-eventos.md)
- [Glossary: zone, track and event](../../../../docs/glossary.md)
- [ADR 0002: persistence and retention](../../../../docs/adr/0002-persistence-and-retention.md)
- [Pipeline data flow](../../../../docs/diagrams.md#flujo-de-datos)
