import argparse
import sys
from pathlib import Path

from .runner import check_folder, run


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Quality evaluator for every Hinglish Editor feature.')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Check an existing result folder against its feature rules')
    check.add_argument('folder')
    go = sub.add_parser('run', help='Run a feature, check it, and redo it with corrections until it passes')
    go.add_argument('--root', default='.')
    go.add_argument('--attempts', type=int, default=3)
    go.add_argument('feature_command', nargs=argparse.REMAINDER,
                    help='after "--": the feature command, e.g. -- -m hinglish_zoom --root . --input x.xml')
    args = parser.parse_args()
    say = lambda m: print(m, flush=True)
    try:
        if args.command == 'check':
            page = check_folder(Path(args.folder), say)
            print(f'Quality report: {page}', flush=True)
            return 0
        command = [a for a in args.feature_command if a != '--']
        if '-m' not in command:
            parser.error('give the feature command after --, e.g. -- -m hinglish_sound --root . --input x.xml')
        result = run(Path(args.root), command, max(1, args.attempts), say)
        return 0 if result else 1
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
