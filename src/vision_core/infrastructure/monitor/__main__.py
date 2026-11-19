"""python main.py --demo-zones --port 8080"""

import argparse
import logging
import os
import signal
from pathlib import Path

from vision_core.features.monitor.infrastructure.http.server import make_server


def main(*, state=None, build_state=None, build_runtime=None, config=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("VISION_CORE_MONITOR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--zones", default=os.getenv("VISION_CORE_ZONES_FILE"))
    parser.add_argument(
        "--uncalibrated",
        action="store_true",
        default=os.getenv("VISION_CORE_MONITOR_UNCALIBRATED", "0") == "1",
        help="Detectar y recordar personas sin inventar zonas ni cruces",
    )
    parser.add_argument(
        "--demo-zones",
        action="store_true",
        default=os.getenv("VISION_CORE_MONITOR_DEMO_ZONES", "0") == "1",
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
        args.zones = str(Path(__file__).resolve().parents[4] / "config/zones.example.json")
    elif not args.zones:
        parser.error("Indica --zones o --demo-zones")
    logging.basicConfig(level=logging.INFO)

    if build_runtime is None:
        raise RuntimeError("build_runtime es obligatorio")
    if state is None:
        if build_state is None:
            raise RuntimeError("build_state es obligatorio")
        state = build_state(demo=args.demo_zones or args.uncalibrated)

    server = None
    runtime = None

    def shutdown():
        if server is not None:
            server.shutdown()

    try:
        # Construir el runtime antes que el server: una config inválida no debe
        # dejar un socket abierto ni un hilo sin cerrar.
        runtime = build_runtime(
            state,
            zones_file=args.zones,
            exit_on_error=os.getenv("VISION_CORE_MONITOR_EXIT_ON_ERROR", "0") == "1",
            on_failure=shutdown,
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
        if runtime is not None:
            runtime.stop()
        if server is not None:
            server.server_close()
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
