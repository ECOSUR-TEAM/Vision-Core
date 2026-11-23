# Changelog

All notable changes to this project are documented here using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [Unreleased]

### Added
- Automated semantic versioning, changelog extraction and GitHub Releases.
- G0 baseline with `camera_id` in profiling and camera-labelled metrics.
- Synthetic integration and 30-second e2e baseline tests with coverage artifacts.
- Performance budgets, deterministic synthetic-video benchmark, baseline comparison and nightly workflow.
- PR performance smoke test with wide thresholds and per-module coverage thresholds.
- Manual edge benchmark matrix for FP32/INT8/FP16 profiles with quality gates and registered precision variants.
- Camera quality and calibration drift monitor with configurable signals, `degraded` status, metrics and non-intrusive monitor warning.
- Event sinks with idempotent webhook delivery, bounded retries, dead-letter, backpressure metrics and documented MQTT port (ADR 0010).
- Optional zone editor in the monitor with versioned HTTP contract, shared schema validation, token gate, atomic writes, mandatory JSONL audit and explicit restart-required response.
- SLO dashboard, alert runbooks and synthetic incident drill harness with snapshot-scoped signals, p95 export and generated evidence artifacts.

### Changed
- Event sink dedupe and shutdown semantics: the key is marked only after a 2xx, drops/dead-letter/shutdown release it for producer retries, `close()` signals the worker before closing the destination, and jitter is applied before the backoff cap.
- Frame buffer mantiene capacidad 1 con política drop-old explícita.
- Rechazo HTTP del monitor drena la petición antes de cerrar para evitar RST en Windows.
- Docker and CI workflows publish and validate versioned artifacts.
- `FrameProfiler` y `STAGES` se importan desde `vision_core.core.telemetry`; el path legacy `vision_core.core.inference.frame_profiler` fue eliminado.
- El contrato canónico `ReIDMemory` vive en `vision_core.core.contracts` y conserva compatibilidad estructural; el puerto duplicado del slice ReID y su re-export fueron eliminados sin shim.
- El registro de modelos vive en `vision_core.core.model_registry`; imports, empaquetado, documentación y guardrails de arquitectura apuntan a la nueva ruta.
- El HTML del monitor se sirve desde `vision_core.features.monitor.infrastructure.http.static`; `package-data` y CODEOWNERS apuntan a la nueva ruta.

### Removed
- Shim `vision_core.features.video.infrastructure.frame_validation`, directorios legacy huérfanos y rutas antiguas del registro de modelos; los imports canónicos son `vision_core.core.validation` y `vision_core.core.model_registry`.
- Tests duplicados de cámara y detección; la cobertura válida queda en los tests de los slices correspondientes.

### Security
- Webhook event sink rejects HTTP redirects, non-public destinations and slow timeouts, validates DNS before each send and warns when TLS verification is disabled.
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
