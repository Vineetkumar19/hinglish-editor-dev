"""Customer entry point. Owner source checkout keeps its existing launch command."""
import argparse
import json
import os
import runpy
import sys
import threading
import webbrowser
from pathlib import Path
from .client import LicenseClient
from .release_config import SERVER_ORIGIN, PUBLIC_KEY

ENGINE_MODULES={'hinglish_clean','hinglish_semantic','hinglish_captions','hinglish_broll','hinglish_visuals',
                'hinglish_zoom','hinglish_sound','hinglish_eyecontact','hinglish_shorts','hinglish_aiimage',
                'hinglish_aivideo','hinglish_motion','hinglish_niche','hinglish_eval'}


def main():
    # Frozen engine subprocesses retain the existing Python -u -m contract.
    if getattr(sys,'frozen',False) and '-m' in sys.argv[1:]:
        index=sys.argv.index('-m');module=sys.argv[index+1]
        if module not in ENGINE_MODULES:raise SystemExit('Unsupported editing engine.')
        folder=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Hinglish Editor'
        LicenseClient(folder/'License',SERVER_ORIGIN,PUBLIC_KEY,os.environ.get('HINGLISH_EDITION','desktop')).ensure()
        sys.argv=[module,*sys.argv[index+2:]]
        runpy.run_module(module,run_name='__main__');return
    parser=argparse.ArgumentParser(description='Hinglish Editor')
    parser.add_argument('--edition',choices=('desktop','plugins'),default='desktop')
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--engine',choices=sorted(ENGINE_MODULES))
    args,remaining=parser.parse_known_args()
    folder=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Hinglish Editor'
    root=folder/'Data';root.mkdir(parents=True,exist_ok=True)
    client=LicenseClient(folder/'License',SERVER_ORIGIN,PUBLIC_KEY,args.edition)
    if args.engine:
        client.ensure()
        sys.argv=[args.engine,*remaining]
        runpy.run_module(args.engine,run_name='__main__');return
    if remaining:parser.error('Unknown launch options.')
    from hinglish_app.server import serve
    engine=Path(sys.executable).with_name('HinglishEngine.exe') if getattr(sys,'frozen',False) else Path(sys.executable)
    if not engine.is_file():raise SystemExit('The editing engine is missing. Reinstall the signed release.')
    server,state=serve(root,8765,python_executable=engine,engine_root=Path(__file__).resolve().parents[1],license_client=client)
    launch=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','hinglish_license.launcher']
    config={'root':str(root),'bridge':'http://127.0.0.1:8765','launcher':launch,
            'engine_root':str(state.engine_root),'edition':args.edition}
    temp=folder/'install.tmp';temp.write_text(json.dumps(config),encoding='utf-8');temp.replace(folder/'install.json')
    if not args.no_open:
        destination='/' if args.edition=='desktop' and client.status()['active'] else '/activation.html?edition='+args.edition
        threading.Timer(.5,lambda:webbrowser.open('http://127.0.0.1:8765'+destination)).start()
    try:server.serve_forever()
    finally:
        if state._cinematic:state._cinematic.close()
        if state._beats:state._beats.pool.shutdown(wait=True)
        server.server_close()


if __name__=='__main__':main()
