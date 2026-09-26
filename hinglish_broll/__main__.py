import argparse
import sys
from pathlib import Path

from .pipeline import run


def main():
    parser = argparse.ArgumentParser(description='Add B-roll to a timeline or video. Local AI planning.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Sequence XML (Premiere/Resolve) or video file/folder')
    parser.add_argument('--format', choices=['instagram_vertical', 'square', 'youtube_horizontal'],
                        help='Canvas for video input (XML input keeps its own sequence size)')
    parser.add_argument('--density', choices=['low', 'medium', 'high'])
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    args = parser.parse_args()
    try:
        result = run(Path(args.root), Path(args.input), args.format, args.density, args.device,
                     progress=lambda m: print(m, flush=True))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
