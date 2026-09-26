import argparse
import sys
from pathlib import Path

from .pipeline import run
from .settings import FREQUENCY, STRENGTH, STYLES, ZoomSettings


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Smart Zoom: face-aware zooms on key moments. Local AI.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Sequence XML (Premiere/Resolve) or video file/folder')
    parser.add_argument('--format', choices=['instagram_vertical', 'square', 'youtube_horizontal'])
    parser.add_argument('--style', choices=STYLES, default='smooth')
    parser.add_argument('--strength', choices=list(STRENGTH), default='medium')
    parser.add_argument('--frequency', choices=list(FREQUENCY), default='medium')
    parser.add_argument('--no-face', action='store_true', help='Zoom into the frame centre instead of the face')
    parser.add_argument('--jump-cuts', action='store_true', help='Also alternate framing on every cut')
    parser.add_argument('--no-jump-cuts', action='store_true', help=argparse.SUPPRESS)   # old default, kept for scripts
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    settings = ZoomSettings(args.style, args.strength, args.frequency, not args.no_face,
                            args.jump_cuts and not args.no_jump_cuts, args.device)
    try:
        result = run(Path(args.root), Path(args.input), args.format, settings, progress=lambda m: print(m, flush=True))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
