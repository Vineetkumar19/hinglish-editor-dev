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
    parser.add_argument('--presentation', choices=['auto', 'fullscreen', 'popup', 'cutout', 'behind'])
    parser.add_argument('--black-background', action='store_true', help='Keep speech, replace existing video with black for visual-search review')
    parser.add_argument('--auto-place', action='store_true', help='Legacy automatic placement instead of five choices per keyword')
    parser.add_argument('--evaluator', choices=['auto', 'vlm', 'clip', 'off'],
                        help='Check every picture/video before use: auto = vision model (Ollama qwen2.5vl) '
                             'when available, else CLIP type check')
    parser.add_argument('--script', type=Path, help='Your script (.txt): fixes misheard names and gives the AI context')
    parser.add_argument('--no-web', action='store_true',
                        help='Only Wikipedia/Wikimedia Commons and stock sites (no search of the whole web)')
    parser.add_argument('--options-per-moment',type=int,choices=[2,5],default=5)
    parser.add_argument('--search-method',choices=['verified','website'],default='verified',
                        help='website: public image options for human review, without stock keys or Vision checks')
    args = parser.parse_args()
    try:
        result = run(Path(args.root), Path(args.input), args.format, args.density, args.device,
                     False if args.no_popups else None, args.brain, progress=lambda m: print(m, flush=True),
                     use_web=False if args.no_web else None, evaluator_choice=args.evaluator,
                     script=args.script.read_text(encoding='utf-8-sig') if args.script else '',
                     presentation=args.presentation, black_background=args.black_background,
                     review_options=not args.auto_place,options_per_moment=args.options_per_moment,
                     search_method=args.search_method)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    import faulthandler
    faulthandler.enable()
    sys.exit(main())
