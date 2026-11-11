import argparse
import sys
from pathlib import Path

from .pipeline import run
from .settings import COUNT_PER_MINUTE, LOOKS, ShortsSettings, parse_time


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Long to Shorts: vertical shorts from the best hook moments of a '
                                                 'long video. Local AI.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Your long video (or a folder of long videos)')
    parser.add_argument('--count', default='medium', help=f'{"/".join(COUNT_PER_MINUTE)} or an exact number (1-40)')
    parser.add_argument('--min', type=float, default=30.0, help='Shortest short in seconds')
    parser.add_argument('--max', type=float, default=60.0, help='Longest short in seconds')
    parser.add_argument('--pieces', type=int, default=3, choices=[1, 2, 3], help='Parts of the long video one short may join')
    parser.add_argument('--look', choices=LOOKS, default='template')
    parser.add_argument('--title', default='', help='Same title on every short (default: the AI writes one per short)')
    parser.add_argument('--handle', default='', help='Channel shown under the video, e.g. @Vineetkumar_19')
    parser.add_argument('--cta', default='WATCH FULL VIDEO ON')
    parser.add_argument('--captions', action='store_true')
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--caption-style', default='typography_1')
    parser.add_argument('--start', default='', help='Only look from this time of the long video (e.g. 2:30)')
    parser.add_argument('--end', default='', help='Only look until this time')
    parser.add_argument('--brain', choices=['auto', 'ollama', 'local'], default='auto')
    parser.add_argument('--script', type=Path, help='Your script (.txt): right names and context for the AI')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--format', help=argparse.SUPPRESS)      # the app sends it to every feature; shorts are 9:16
    args = parser.parse_args()
    try:
        settings = ShortsSettings(count=args.count, min_length=args.min, max_length=args.max, pieces=args.pieces,
                                  look=args.look, title=args.title, handle=args.handle, cta=args.cta,
                                  captions=args.captions, fresh=args.fresh, caption_style=args.caption_style,
                                  start=parse_time(args.start), end=parse_time(args.end), device=args.device,
                                  brain=args.brain)
        script = args.script.read_text(encoding='utf-8-sig') if args.script else ''
        result = run(Path(args.root), Path(args.input), settings, progress=lambda m: print(m, flush=True), script=script)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
