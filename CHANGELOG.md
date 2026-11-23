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
- Optional zone editor in the monitor with versioned HTTP contract, shared schema validation, token gate, atomic writes, mandatory JSONL audit and explicit restart-required response.
- SLO dashboard, alert runbooks and synthetic incident drill harness with snapshot-scoped signals, p95 export and generated evidence artifacts.

### Changed
- Frame buffer mantiene capacidad 1 con política drop-old explícita.
- Rechazo HTTP del monitor drena la petición antes de cerrar para evitar RST en Windows.
- Docker and CI workflows publish and validate versioned artifacts.
- `FrameProfiler` y `STAGES` se importan desde `vision_core.core.telemetry`; el path legacy `vision_core.core.inference.frame_profiler` fue eliminado.
- El contrato canónico `ReIDMemory` vive en `vision_core.core.contracts` y conserva compatibilidad estructural; el puerto duplicado del slice ReID y su re-export fueron eliminados sin shim.

### Security
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
