"""Serve the engine build without starting publishing or background recovery."""
import argparse
from pathlib import Path
from hinglish_app.server import serve

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8912);args=parser.parse_args()
    server,state=serve(Path(__file__).resolve().parents[1],args.port)
    print(f'Motion engine studio: http://127.0.0.1:{server.server_port}/?tool=motion',flush=True)
    try:server.serve_forever()
    finally:server.server_close()
