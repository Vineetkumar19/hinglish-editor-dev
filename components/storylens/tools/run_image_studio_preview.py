"""Visible image-workspace validation without restarting the owner's main app.

No publishing worker, workflow supervisor, bridge registration or resume work.
The shared GPU lock still serializes generation with the main application.
"""
import os
from pathlib import Path
from hinglish_app.server import AppState,LocalHTTPServer,make_handler

root=Path(__file__).resolve().parents[1]
state=AppState(root,8864)
server=LocalHTTPServer(('127.0.0.1',8864),make_handler(state))
evidence=root/'output/aiimage/channel-studio-evidence'
evidence.mkdir(parents=True,exist_ok=True)
(evidence/'preview-service.pid').write_text(str(os.getpid()),'utf-8')
print('Storylens image studio preview: http://127.0.0.1:8864/?tool=thumbnail',flush=True)
server.serve_forever()
