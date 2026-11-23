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
- Camera quality and calibration drift monitor with configurable signals, `degraded` status, metrics and non-intrusive monitor warning.

### Changed
- Frame buffer mantiene capacidad 1 con política drop-old explícita.
- Rechazo HTTP del monitor drena la petición antes de cerrar para evitar RST en Windows.
- Docker and CI workflows publish and validate versioned artifacts.

### Security
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
