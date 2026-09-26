import argparse
from pathlib import Path
import sys
import webbrowser

from .pipeline import run
from .styles import TEMPLATES


def main(argv=None):
    parser = argparse.ArgumentParser(description='Create premium animated Roman Hinglish captions locally')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--style', choices=sorted(TEMPLATES), default='flash_cut')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--format', choices=['source', 'instagram_vertical', 'square', 'youtube_horizontal'], default='source')
    parser.add_argument('--script', type=Path, help='Optional loose reference script for spelling')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args(argv)
    try:
        reference = args.script.read_text(encoding='utf-8-sig') if args.script else ''
        output = run(args.root, args.input, args.style, args.device,
                     None if args.format == 'source' else args.format, lambda value: print(value, flush=True),
                     reference_script=reference)
        page = output / 'index.html'
        print(f'Results: {page}', flush=True)
        if args.open: webbrowser.open(page.as_uri())
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print('Could not complete: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
