# Camera health slice

This slice observes image quality and calibration drift without changing the
door-event semantics. It samples the frame already produced by the pipeline,
classifies a stable reason and publishes a non-blocking `degraded` state.

## Documentation

- [Camera quality and drift guide](../../../../docs/camera-quality.md)
- [Versioned API contracts](../../../../docs/api-contracts.md)
- [Observability: health, ready and metrics](../../../../docs/observability.md)
- [ADR 0009: non-intrusive camera quality](../../../../docs/adr/0009-calidad-de-camara-no-intrusiva.md)
