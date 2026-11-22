"""python main.py --demo-zones --port 8080"""

import argparse
import signal
from pathlib import Path

from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.settings import Settings
from vision_core.shared.observability.structured_logging import configure_structured_logging


def _normalize_monitor_host(host):
    normalized = str(host).strip()
    if normalized in {"", "0"}:
        return "0.0.0.0"
    return normalized


def _is_exposed_monitor_host(host):
    return _normalize_monitor_host(host) == "0.0.0.0"


def main(*, state=None, build_state=None, build_runtime=None, config=None):
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
    parser.add_argument(
        "--no-render",
        action="store_true",
        default=False,
        help="Omitir render/JPEG por completo (sin visor conectado)",
    )
    args = parser.parse_args()
    args.host = _normalize_monitor_host(args.host)
    if not args.host:
        parser.error("Host inválido")
    if _is_exposed_monitor_host(args.host):
        print("WARNING: binding to 0.0.0.0 exposes monitor without auth; use only with ticket 42 controls.", flush=True)
    if not 1 <= args.port <= 65535:
        parser.error("Puerto inválido")
    if args.uncalibrated:
        args.zones = None
    elif args.demo_zones:
        args.zones = str(Path(__file__).resolve().parents[4] / "config/zones.example.json")
    elif not args.zones:
        parser.error("Indica --zones o --demo-zones")
    if build_runtime is None:
        raise RuntimeError("build_runtime es obligatorio")
    if state is None:
        if build_state is None:
            raise RuntimeError("build_state es obligatorio")
        state = build_state(demo=args.demo_zones or args.uncalibrated, settings=settings)

    server = None
    runtime = None

    def shutdown():
        if server is not None:
            server.shutdown()

    try:
        runtime = build_runtime(
            state,
            zones_file=args.zones,
            exit_on_error=settings.monitor.exit_on_error,
            on_failure=shutdown,
            settings=settings,
            render_enabled=False if args.no_render else None,
            config=config,
        )
        server = make_server(args.host, args.port, state)

        def terminate(*_):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, terminate)
        print(f"Vision Core: http://{args.host}:{args.port}", flush=True)
        runtime.start()
        server.serve_forever(poll_interval=0.25)
    except ValueError as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        pass
    finally:
        if runtime is not None:
            runtime.stop()
        if server is not None:
            server.server_close()
        if runtime is not None:
            runtime.join(timeout=2)
    if runtime is not None and runtime.failed.is_set():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
