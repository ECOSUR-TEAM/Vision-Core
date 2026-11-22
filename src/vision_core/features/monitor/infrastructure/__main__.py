"""python main.py --demo-zones --port 8080"""

import argparse
import signal
import sys
from pathlib import Path

from vision_core.core.config import Settings
from vision_core.core.telemetry.structured_logging import configure_structured_logging
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.model_registry.activation import resolve_active_models


def main(*, state=None, build_state=None, build_runtime=None, config=None):
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        argparse.ArgumentParser(description=__doc__).parse_args()
    settings = Settings.from_env(validate_startup=state is None or build_runtime is None)
    active_models = resolve_active_models(settings)
    configure_structured_logging(
        settings.logging.level,
        settings.logging.json_format,
        settings.logging.camera_id,
        active_models.as_log_identity(),
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
    if not 1 <= args.port <= 65535:
        parser.error("Puerto inválido")
    if args.uncalibrated:
        args.zones = None
    elif args.demo_zones:
        args.zones = str(Path(__file__).resolve().parents[5] / "config/zones.example.json")
    elif not args.zones:
        parser.error("Indica --zones o --demo-zones")
    if build_runtime is None:
        raise RuntimeError("build_runtime es obligatorio")
    if state is None:
        if build_state is None:
            raise RuntimeError("build_state es obligatorio")
        state = build_state(demo=args.demo_zones or args.uncalibrated, settings=settings, models=active_models)

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
            models=active_models,
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
