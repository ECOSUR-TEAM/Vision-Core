# Detection slice

This feature is the template for future vertical slices.

- `domain/` contains the feature entity and port only.
- `application/` exposes use cases through immutable request/response DTOs.
- `infrastructure/` contains adapters and dependency construction.
- Application code depends on domain ports, never on infrastructure adapters.
- DTOs contain transport data only; mapping belongs in `application/mappers/`.

New slices should preserve these three layers and dependency direction. A
deviation must be justified in its pull request.
