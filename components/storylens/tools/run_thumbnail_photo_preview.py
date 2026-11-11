"""Visible Storylens validation; no supervisors, publishing or bridge registration."""
from pathlib import Path
from hinglish_app.server import AppState,LocalHTTPServer,make_handler

root=Path(__file__).resolve().parents[1]
state=AppState(root,8866)
server=LocalHTTPServer(('127.0.0.1',8866),make_handler(state))
print('Storylens real-photo preview: http://127.0.0.1:8866/?tool=thumbnail',flush=True)
server.serve_forever()
