"""Start just the Editor Handoff screen, without Storylens background workers."""
import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import secrets
from types import SimpleNamespace
from urllib.parse import urlsplit
import webbrowser

from hinglish_app.server import AppState, make_handler


ROOT = Path(__file__).resolve().parents[2]
STATIC = {'/editor-link.html', '/editor-link.css', '/editor-link.js',
          '/workbench.css', '/feedback.js', '/icons.js', '/resolve-logo.png', '/tool-layout.css',
          '/embedded-tool.js', '/editor-handoff.css', '/editor-handoff.js', '/api/pick'}
ACTIONS = {'/api/editor-link/prepare', '/api/editor-link/apply', '/api/editor-link/capcut-drafts'}


def serve(port, open_browser):
    state = SimpleNamespace(root=ROOT, port=port, token=secrets.token_urlsafe(32),
                            license_client=None, static=ROOT/'hinglish_app/static')
    state.pick = lambda kind: AppState.pick(state, kind)
    base = make_handler(state)

    class Handler(base):
        def do_GET(self):
            if self.path == '/':
                self.path = '/editor-link.html'
            if urlsplit(self.path).path not in STATIC:
                return self.send_error(404)
            return super().do_GET()

        def do_POST(self):
            if urlsplit(self.path).path not in ACTIONS:
                return self.send_error(404)
            return super().do_POST()

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as http:
        url = f'http://127.0.0.1:{port}/editor-link.html'
        print(url, flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            http.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8883)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    serve(args.port, not args.no_browser)
