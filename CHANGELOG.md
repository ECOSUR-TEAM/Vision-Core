# Changelog

All notable changes to this project are documented here using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [Unreleased]

### Added
- Typed, validated environment settings.
- JSON structured logs, metrics and health/readiness endpoints.
- Automated Dependabot, CodeQL and dependency-review supply-chain controls.

### Changed
- Docker and CI workflows publish and validate versioned artifacts.

### Fixed
- Default model path validation no longer blocks tests and unrelated adapters.

### Security
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
