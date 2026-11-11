import argparse
import json
import time
from pathlib import Path

from .service import Publisher


def main(argv=None):
    parser = argparse.ArgumentParser(description='Hinglish Editor folder publishing queue')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('folders')
    commands.add_parser('status')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('name', help='Exact video name, or Upload <name> on YouTube')
    prepare.add_argument('--shorts', action='store_true')
    commands.add_parser('worker')
    connect = commands.add_parser('connect-youtube')
    connect.add_argument('client_file', type=Path)
    args = parser.parse_args(argv)
    publisher = Publisher(args.root)
    if args.action == 'folders':
        print(json.dumps(publisher.init_folders(), indent=2))
    elif args.action == 'status':
        print(json.dumps(publisher.snapshot(), ensure_ascii=False, indent=2))
    elif args.action == 'prepare':
        result = publisher.prepare({'name': args.name, 'make_shorts': args.shorts})
        print(json.dumps(result, indent=2))
    elif args.action == 'connect-youtube':
        from .providers import connect_youtube
        print(json.dumps(connect_youtube(args.root, args.client_file), indent=2))
    else:
        publisher.start()
        print('Publisher worker running. Approved jobs only; Ctrl+C stops it.')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            publisher.stop.set()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
