import argparse
import sys
from pathlib import Path

from .pipeline import run
from .settings import STYLES


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Sound design: music + effects by meaning. Local AI.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Sequence XML or video file/folder')
    parser.add_argument('--format', choices=['instagram_vertical', 'square', 'youtube_horizontal'])
    parser.add_argument('--style', choices=STYLES)
    parser.add_argument('--density', choices=['low', 'medium', 'high'])
    parser.add_argument('--no-music', action='store_true')
    parser.add_argument('--no-effects', action='store_true')
    parser.add_argument('--no-transitions', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--script', type=Path, help='Your script (.txt): fixes misheard names and gives the AI context')
    args = parser.parse_args()
    overrides = {'style': args.style, 'density': args.density, 'device': args.device,
                 'music': False if args.no_music else None, 'effects': False if args.no_effects else None,
                 'transitions': False if args.no_transitions else None}
    try:
        result = run(Path(args.root), Path(args.input), args.format, overrides, progress=lambda m: print(m, flush=True),
                     script=args.script.read_text(encoding='utf-8-sig') if args.script else '')
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
