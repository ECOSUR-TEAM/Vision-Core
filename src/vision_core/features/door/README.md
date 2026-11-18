# Door slice

The door feature keeps zone-crossing behavior behind a domain port.

- `domain/` contains the analytics port and zone observations.
- `application/` exposes `UpdateZone` and `GetHistory` through immutable DTOs.
- `infrastructure/` contains polygon analytics, zone configuration, validation,
  loading, and dependency construction.
- Shared `Polygon` and `Event` types come from `vision_core.shared`.

The same three-layer structure is used by the detection pilot and should be
preserved by future vertical slices.
