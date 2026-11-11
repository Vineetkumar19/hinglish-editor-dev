import argparse
import json
from pathlib import Path
import sys
import webbrowser
from .detection import CleanSettings
from .pipeline import run


def main(argv=None):
    parser = argparse.ArgumentParser(description='Remove silence locally, with CPU or NVIDIA CUDA speech detection.')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--input', type=Path, help='One video or a folder; default input/phase1 folders')
    parser.add_argument('--format', choices=['source', 'instagram_vertical', 'youtube_horizontal'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--device',choices=('cpu','cuda'))
    parser.add_argument('--xml-only', action='store_true', help='Skip MP4 encoding for a faster Premiere workflow')
    parser.add_argument('--open', action='store_true', help='Open the results page when finished')
    args = parser.parse_args(argv)
    try:
        config = args.config or args.root / 'config.phase1.json'
        settings = CleanSettings(**json.loads(config.read_text(encoding='utf-8-sig'))) if config.exists() else CleanSettings()
        from hinglish_cut.model_preferences import preferred_device
        settings.device=args.device or preferred_device(args.root)
        batch, entries = run(args.root, settings, args.input, args.format, not args.xml_only,
                             lambda message: print(message, flush=True))
        print(f'\nResults: {batch / "index.html"}', flush=True)
        if args.open:
            webbrowser.open((batch / 'index.html').as_uri())
        return 0 if all(e['status'] == 'READY_FOR_REVIEW' for e in entries) else 2
    except KeyboardInterrupt:
        print('\nStopped. Completed speech analysis is saved for the next run.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Could not complete: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
