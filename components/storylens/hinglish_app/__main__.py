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
    parser.add_argument('--no-publisher-worker', action='store_true',
                        help='Run the editor without starting scheduled publishing')
    parser.add_argument('--no-publish-bridge', action='store_true',
                        help='Keep the primary editor bridge pointed at its existing service')
    parser.add_argument('--no-supervisor', action='store_true',
                        help='Do not run the shared workflow continuation supervisor')
    parser.add_argument('--upload-workflow-supervisor', action='store_true',
                        help='Recover explicitly authorized uploading workflows independently of other workflows')
    parser.add_argument('--desktop', action='store_true', help='Start the desktop engine without automatic background jobs')
    args = parser.parse_args(argv)
    if args.desktop:
        args.no_open = args.no_publisher_worker = args.no_supervisor = True
        args.upload_workflow_supervisor = False
    try:
        server, state = serve(args.root, args.port, publish_bridge=not args.no_publish_bridge,
                              restore_pending_jobs=not args.desktop)
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
    analytics_stop = None
    finance_server = None
    if state.port == DEFAULT_PORT:
        from .finance import start as start_finance
        finance_server = start_finance()
        if not args.desktop:
            from .analytics_http import service as analytics_service
            analytics_stop = analytics_service(state).schedule()

    from .social_comments import SocialComments
    import sqlite3
    try:
        if not args.desktop and SocialComments.has_enabled_accounts(state.root):
            from .agents_http import service
            service(state).comments
    except sqlite3.Error:
        print('Saved comment automation could not resume; check the AI Agents inbox.', flush=True)
    from .assistant_pipeline import supervise
    workflow_stop=threading.Event()
    if not args.no_supervisor:
        threading.Thread(target=supervise,args=(state.assistant,workflow_stop),
                         name='storylens-workflow-supervisor',daemon=True).start()
    elif args.upload_workflow_supervisor:
        from .assistant_upload_workflow import supervise as upload_supervise
        threading.Thread(target=upload_supervise,args=(state.assistant,workflow_stop),
                         name='storylens-upload-workflow-supervisor',daemon=True).start()
    if not args.no_publisher_worker:
        try:
            state.publisher.start()
        except RuntimeError as error:
            print(f'Publishing worker: {error}', flush=True)
    if not args.no_open:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        workflow_stop.set()
        if analytics_stop is not None:
            analytics_stop.set()
        if finance_server is not None:
            finance_server.shutdown()
            finance_server.server_close()
        comment_service=getattr(getattr(state,'_agent_suite',None),'_comments',None)
        if comment_service is not None:comment_service.stop()
        if state._cinematic: state._cinematic.close()
        if state._beats: state._beats.pool.shutdown(wait=True)
        if state._publisher is not None: state._publisher.stop.set()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
