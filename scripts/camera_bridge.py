"""Host-side TCP bridge for the camera; never changes host firewall rules."""
import asyncio
import os
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RELAY_HOST = os.environ.get('CAMERA_BRIDGE_RELAY_HOST', 'host.docker.internal')
RELAY_BIND = os.environ.get('CAMERA_BRIDGE_BIND', RELAY_HOST)
RELAY_CHECK_HOST = os.environ.get('CAMERA_BRIDGE_CHECK_HOST', RELAY_HOST)
RELAY_PORT = 15554


def camera_target(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'rtsp' or not parsed.hostname:
        raise ValueError('FRIGATE_CAMERA_RTSP_URL debe ser una URL rtsp válida')
    return parsed.hostname, parsed.port or 554


def relay_url(url):
    camera_target(url)
    parsed = urlsplit(url)
    credentials = parsed.netloc.rsplit('@', 1)[0] + '@' if '@' in parsed.netloc else ''
    return urlunsplit((parsed.scheme, f'{credentials}{RELAY_HOST}:{RELAY_PORT}',
                       parsed.path, parsed.query, parsed.fragment))


async def forward(reader, writer):
    while data := await reader.read(65536):
        writer.write(data)
        await writer.drain()


async def serve(target, bind):
    async def client(reader, writer):
        upstream = None
        tasks = []
        try:
            remote, upstream = await asyncio.wait_for(asyncio.open_connection(*target), timeout=5)
            tasks = [asyncio.create_task(forward(reader, upstream)),
                     asyncio.create_task(forward(remote, writer))]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, asyncio.TimeoutError):
            pass  # Never log URLs/credentials or payloads.
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for connection in (writer, upstream):
                if connection is not None:
                    connection.close()
                    try:
                        await connection.wait_closed()
                    except OSError:
                        pass
    server = await asyncio.start_server(client, bind, RELAY_PORT)
    print('Puente de cámara listo (TCP).', flush=True)
    async with server:
        await server.serve_forever()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if mode == 'init-config':
        destination = Path('/config/config.yml')
        if not destination.exists():
            shutil.copyfile('/defaults/config.yml', destination)
        return
    url = os.environ['FRIGATE_CAMERA_RTSP_URL']
    if mode == 'frigate':
        os.environ['FRIGATE_CAMERA_RTSP_URL'] = relay_url(url)
        os.execv('/init', ['/init'])
    target = camera_target(url)
    if mode == 'check':
        # Ensure both the host bridge and the actual camera are reachable.
        check_host = '127.0.0.1' if RELAY_CHECK_HOST in ('0.0.0.0', '::') else socket.gethostbyname(RELAY_CHECK_HOST)
        for address in ((check_host, RELAY_PORT), target):
            with socket.create_connection(address, timeout=3):
                pass
    elif mode == 'serve':
        bind = RELAY_BIND if RELAY_BIND in ('0.0.0.0', '::') else socket.gethostbyname(RELAY_BIND)
        asyncio.run(serve(target, bind))
    else:
        raise ValueError('Modo desconocido')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Puente de cámara: {type(error).__name__}. Revisa cámara y configuración.', file=sys.stderr)
        raise SystemExit(1)
