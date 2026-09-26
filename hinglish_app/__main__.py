from pathlib import Path
import argparse
import sys
import threading
import urllib.request
import webbrowser

from . import DEFAULT_PORT
from .server import serve


def main(argv=None):
    parser = argparse.ArgumentParser(description='Hinglish Editor local dashboard and plugin bridge')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args(argv)
    try:
        server, _ = serve(args.root, args.port)
    except OSError as error:
        url = f'http://127.0.0.1:{args.port}/'
        try:
            with urllib.request.urlopen(url + 'api/health', timeout=1) as response:
                if response.status == 200:
                    print(f'Hinglish Editor is already running: {url}', flush=True)
                    if not args.no_open:
                        webbrowser.open(url)
                    return 0
        except Exception:
            pass
        print(f'Could not start the app: {error}', file=sys.stderr)
        return 1
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Hinglish Editor is ready: {url}', flush=True)
    if not args.no_open:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
