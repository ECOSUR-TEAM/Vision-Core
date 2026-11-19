"""python main.py --demo-zones --port 8080"""

import argparse
import logging
import signal
from pathlib import Path

from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.settings import Settings


def main(*, state=None, build_state=None, build_runtime=None):
    settings = Settings.from_env(validate_startup=state is None or build_runtime is None)
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
    logging.basicConfig(level=getattr(logging, settings.logging.level))

    if build_runtime is None:
        raise RuntimeError("build_runtime es obligatorio")
    if state is None:
        if build_state is None:
            raise RuntimeError("build_state es obligatorio")
        state = build_state(demo=args.demo_zones or args.uncalibrated)

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
