# Video slice

`domain/` holds the video source port, `application/` exposes frame capture
through immutable DTOs, and `infrastructure/` contains the RTSP and file
adapters plus the latest-frame source.

Only the most recent frame is kept: older frames are discarded instead of
growing an unbounded queue. RTSP TCP is the default transport.

## Documentation

- [Pipeline data flow](../../../../docs/diagrams.md#flujo-de-datos)
- [Configuration: video and RTSP](../../../../docs/configuration.md#video-y-rtsp)
- [Runbook: camera down or unstable RTSP](../../../../docs/runbooks/02-camara-caida-o-rtsp-inestable.md)
- [Runbook: low FPS or high latency](../../../../docs/runbooks/05-fps-bajo-o-latencia-alta.md)
- [Frigate and restream guide](../../../../docs/frigate.md)
