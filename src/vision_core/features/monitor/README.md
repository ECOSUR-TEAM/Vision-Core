# Monitor slice

The monitor feature owns telemetry state, frame rendering, and its HTTP
transport. Its application layer exposes state publication and read use cases
through DTOs; the composition root injects the pipeline callbacks and state.

The feature deliberately has no domain ports: the monitor consumes already
resolved pipeline data through application use cases, so no additional domain
contract is required.

## Documentation

- [Monitor guide](../../../../docs/monitor.md)
- [Camera quality and drift guide](../../../../docs/camera-quality.md)
- [Versioned API contracts](../../../../docs/api-contracts.md)
- [Observability: health, ready and metrics](../../../../docs/observability.md)
- [Runbooks index](../../../../docs/runbooks/README.md)
- [ADR 0005: observability and errors](../../../../docs/adr/0005-observabilidad-y-contratos-versionados.md)
