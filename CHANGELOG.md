# Changelog

All notable changes to this project are documented here using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [Unreleased]

### Added
- Automated semantic versioning, changelog extraction and GitHub Releases.
- G0 baseline with `camera_id` in profiling and camera-labelled metrics.
- Synthetic integration and 30-second e2e baseline tests with coverage artifacts.

### Changed
- Bounded frame buffer now enforces an explicit drop-old capacity of 1 or 2.
- Docker and CI workflows publish and validate versioned artifacts.

### Fixed
- Windows TCP reset flakiness when the monitor rejects requests without reading their body.

### Security
- Trivy image scanning and SARIF upload for fixable high and critical findings.

## [0.1.0] - 2026-11-19

### Added
- Initial monitor, detection, ReID and attendance pipeline.
- Docker Compose deployments for camera and webcam modes.
- CI tests and lint workflows.
