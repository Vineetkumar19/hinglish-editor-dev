"""Bounded real yt-dlp transport benchmark; no models, Adobe or production jobs."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yt_dlp import YoutubeDL
from yt_dlp.downloader.dash import DashSegmentsFD

BASE = ROOT / 'output/downloader-performance-20261103'
BASE.mkdir(parents=True, exist_ok=True)
# Actual already-verified H.264/AAC media, partitioned into byte fragments.
source = ROOT / 'output/downloader-queue-20261103/section-check/source-section.mp4'
data = source.read_bytes()
parts = [data[i:i+max(1, len(data)//24)] for i in range(0, len(data), max(1, len(data)//24))]
active = peak = 0
lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        global active, peak
        part = parts[int(self.path.lstrip('/'))]
        with lock:
            active += 1; peak = max(peak, active)
        try:
            time.sleep(.1)  # Fixed per-request latency, identical for each run.
            self.send_response(200); self.send_header('Content-Length', str(len(part))); self.end_headers()
            self.wfile.write(part)
        finally:
            with lock: active -= 1

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
results = []
try:
    for connections in (2, 6):
        peak = 0
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temp:
            dest = Path(temp) / 'source.mp4'; updates = []; last = [-float('inf')]
            def hook(d):
                now = time.monotonic()
                if d['status'] == 'finished' or now-last[0] >= .5:
                    updates.append(d.get('downloaded_bytes')); last[0] = now
            opts = {'quiet':True, 'no_warnings':True, 'noprogress':True,
                    'concurrent_fragment_downloads':connections, 'skip_unavailable_fragments':False,
                    'buffersize':65536, 'continuedl':True}
            started = time.monotonic()
            with YoutubeDL(opts) as ydl:
                downloader = DashSegmentsFD(ydl, opts); downloader.add_progress_hook(hook)
                ok = downloader.download(str(dest), {'url':f'http://127.0.0.1:{server.server_port}/0',
                    'fragments':[{'url':f'http://127.0.0.1:{server.server_port}/{i}'} for i in range(len(parts))],
                    'ext':'mp4', 'protocol':'http_dash_segments'})
            elapsed = time.monotonic()-started
            assert ok and dest.read_bytes() == data
            results.append({'connections':connections, 'seconds':round(elapsed,3), 'peak_requests':peak,
                            'progress_updates':len(updates), 'bytes':len(data),
                            'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
finally:
    server.shutdown(); server.server_close()

result = {'scope':'Real installed yt-dlp fragment transport over controlled localhost HTTP with fixed latency; not a YouTube speed guarantee.',
          'results':results, 'relative_speed':round(results[0]['seconds']/results[1]['seconds'],2)}
(BASE / 'transport-benchmark.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
