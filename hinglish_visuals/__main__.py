import argparse
import sys
from pathlib import Path

from .pipeline import run


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Smart Visuals: real photos, logos and footage of what you talk about.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Sequence XML (Premiere/Resolve) or video file/folder')
    parser.add_argument('--format', choices=['instagram_vertical', 'square', 'youtube_horizontal'],
                        help='Canvas for video input (XML input keeps its own sequence size)')
    parser.add_argument('--density', choices=['low', 'medium', 'high'])
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--brain', choices=['auto', 'ollama', 'local'],
                        help='auto: Ollama thinking model when running, else the built-in local model')
    parser.add_argument('--no-popups', action='store_true', help='Show logos and faces full screen instead of pop-ups')
    parser.add_argument('--evaluator', choices=['auto', 'vlm', 'clip', 'off'],
                        help='Check every picture/video before use: auto = vision model (Ollama qwen2.5vl) '
                             'when available, else CLIP type check')
    parser.add_argument('--no-web', action='store_true',
                        help='Only Wikipedia/Wikimedia Commons and stock sites (no search of the whole web)')
    args = parser.parse_args()
    try:
        result = run(Path(args.root), Path(args.input), args.format, args.density, args.device,
                     False if args.no_popups else None, args.brain, progress=lambda m: print(m, flush=True),
                     use_web=False if args.no_web else None, evaluator_choice=args.evaluator)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
