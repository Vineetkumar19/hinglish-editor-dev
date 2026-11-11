import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', choices=('gaming', 'thumbnail'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--minutes', type=int, default=15)
    parser.add_argument('--no-memes', action='store_true')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--script', type=Path)
    parser.add_argument('--portrait', type=Path)
    parser.add_argument('--background', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--generate', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--design', type=Path)
    args = parser.parse_args()
    if args.tool == 'gaming':
        from .gaming import run
        page = run(args.root, args.input, args.minutes, not args.no_memes, args.device)
    else:
        from .thumbnail import run
        topic = args.script.read_text(encoding='utf-8') if args.script else ''
        import json
        design=json.loads(args.design.read_text('utf-8')) if args.design else None
        page = run(args.root, topic, args.portrait, args.background, args.generate, design=design, reference=args.reference)
    print('Results: ' + str(page.resolve()))


if __name__ == '__main__':
    main()
