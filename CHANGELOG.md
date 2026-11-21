# Changelog

All notable changes to this project are documented here using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [Unreleased]

### Added
- Automated semantic versioning, changelog extraction and GitHub Releases.
- Performance budgets, deterministic synthetic-video benchmark, baseline comparison and nightly workflow.
- Integration/e2e coverage for the synthetic pipeline and monitor health/metrics endpoints.
- PR performance smoke test with wide thresholds and per-module coverage thresholds.

### Changed
- Docker and CI workflows publish and validate versioned artifacts.

### Security
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
