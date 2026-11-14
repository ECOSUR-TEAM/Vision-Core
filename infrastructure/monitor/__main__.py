"""python -m infrastructure.monitor --demo-zones --port 8080"""
import argparse
import logging
import os
import signal
from pathlib import Path

from .http_server import make_server


def main(*, state=None, build_runtime=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--zones', default=os.getenv('VISION_CORE_ZONES_FILE'))
    parser.add_argument('--uncalibrated', action='store_true',
                        default=os.getenv('VISION_CORE_MONITOR_UNCALIBRATED', '0') == '1',
                        help='Detectar y recordar personas sin inventar zonas ni cruces')
    parser.add_argument('--demo-zones', action='store_true',
                        default=os.getenv('VISION_CORE_MONITOR_DEMO_ZONES', '0') == '1',
                        help='Zonas ilustrativas de 640 × 480 para webcam')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Puerto inválido')
    if args.uncalibrated:
        args.zones = None
    elif args.demo_zones:
        args.zones = str(Path(__file__).resolve().parents[2] / 'config/zones.example.json')
    elif not args.zones:
        parser.error('Indica --zones o --demo-zones')
    logging.basicConfig(level=logging.INFO)

    if state is None or build_runtime is None:
        # The composition root lives outside this infrastructure package.
        from composition import build_monitor_runtime, build_monitor_state

        if state is None:
            state = build_monitor_state(demo=args.demo_zones or args.uncalibrated)
        if build_runtime is None:
            build_runtime = build_monitor_runtime

    server = make_server(args.host, args.port, state)
    runtime = build_runtime(
        state,
        zones_file=args.zones,
        exit_on_error=os.getenv('VISION_CORE_MONITOR_EXIT_ON_ERROR', '0') == '1',
        on_failure=server.shutdown,
    )
    runtime.start()
    def terminate(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    print(f'Vision Core: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        server.server_close()
        runtime.join(timeout=2)
    if runtime.failed.is_set():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
