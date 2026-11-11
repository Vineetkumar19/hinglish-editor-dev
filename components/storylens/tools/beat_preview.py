"""Development preview of the local editor; publishing workers are not started."""
from pathlib import Path
from hinglish_app.server import serve

if __name__ == '__main__':
    server, state = serve(Path(__file__).resolve().parents[1], 8769)
    print('Beat Studio preview: http://127.0.0.1:8769/beats.html', flush=True)
    try:
        server.serve_forever()
    finally:
        if state._cinematic: state._cinematic.close()
        if state._beats: state._beats.pool.shutdown(wait=True)
        server.server_close()
