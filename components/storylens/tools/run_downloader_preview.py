"""Serve downloader validation without restarting the shared editor or bridge."""
from pathlib import Path
from hinglish_app.server import AppState,LocalHTTPServer,make_handler
root=Path(__file__).resolve().parents[1]
state=AppState(root,8791)
server=LocalHTTPServer(('127.0.0.1',8791),make_handler(state))
print('Downloader validation at http://127.0.0.1:8791/downloader.html',flush=True)
server.serve_forever()
