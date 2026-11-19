"""python -m vision_core.infrastructure.monitor --demo-zones --port 8080"""

import argparse
import signal
from pathlib import Path

from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.settings import Settings
from vision_core.shared.observability.structured_logging import configure_structured_logging


def main(*, state=None, build_runtime=None):
    settings = Settings.from_env(validate_startup=state is None or build_runtime is None)
    configure_structured_logging(
        settings.logging.level,
        settings.logging.json_format,
        settings.logging.camera_id,
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=settings.monitor.host)
    parser.add_argument("--port", type=int, default=settings.monitor.port)
    parser.add_argument("--zones", default=str(settings.zones.zones_file) if settings.zones.zones_file else None)
    parser.add_argument(
        "--uncalibrated",
        action="store_true",
        default=settings.zones.uncalibrated,
        help="Detectar y recordar personas sin inventar zonas ni cruces",
    )
    parser.add_argument(
        "--demo-zones",
        action="store_true",
        default=settings.zones.demo_zones,
        help="Zonas ilustrativas de 640 × 480 para webcam",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Puerto inválido")
    if args.uncalibrated:
        args.zones = None
    elif args.demo_zones:
        args.zones = str(Path(__file__).resolve().parents[4] / "config/zones.example.json")
    elif not args.zones:
        parser.error("Indica --zones o --demo-zones")
    if state is None or build_runtime is None:
        # The composition root lives outside this infrastructure package.
        from vision_core.composition import build_monitor_runtime, build_monitor_state

        if state is None:
            state = build_monitor_state(demo=args.demo_zones or args.uncalibrated, settings=settings)
        if build_runtime is None:
            build_runtime = build_monitor_runtime

    server = make_server(args.host, args.port, state)
    runtime = build_runtime(
        state,
        zones_file=args.zones,
        exit_on_error=settings.monitor.exit_on_error,
        on_failure=server.shutdown,
    )
    runtime.start()

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    print(f"Vision Core: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        server.server_close()
        runtime.join(timeout=2)
    if runtime.failed.is_set():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
