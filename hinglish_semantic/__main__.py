import argparse
import json
from pathlib import Path
import sys
import webbrowser
from .core import SemanticSettings


def main(argv=None):
    parser = argparse.ArgumentParser(description='Phase 2 semantic assembly / Clean+ fillers and retakes. Local inference.')
    parser.add_argument('mode', choices=['assemble', 'clean-plus', 'prepare', 'apply'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--input', type=Path)
    parser.add_argument('--script', type=Path)
    parser.add_argument('--choices', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--format', choices=['source', 'instagram_vertical', 'youtube_horizontal'])
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--order', choices=['auto', 'continuous', 'chunks'])
    parser.add_argument('--pacing', choices=['tight', 'natural', 'relaxed'])
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = args.config or args.root / 'config.phase2.json'
        data = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
        if args.device: data['device'] = args.device
        if args.order: data['order'] = args.order
        if args.pacing: data['pacing'] = args.pacing
        if args.mode == 'clean-plus':
            data['speech_backend'] = 'swift'
            data['matching_backend'] = 'word_coverage'
        settings = SemanticSettings(**data)
        if args.mode == 'prepare':
            from .models import prepare_models
            prepare_models(args.root, settings)
            print('Meaning models ready. Normal runs are local/offline.')
            return 0
        from .pipeline import run_assembly, run_cleanup, apply_choices
        if args.mode != 'apply':
            from .models import require_models
            require_models(args.root, settings)
        progress = lambda message: print(message, flush=True)
        if args.mode == 'assemble':
            output, report = run_assembly(args.root, settings, args.input, args.script, args.format, progress)
        elif args.mode == 'clean-plus':
            output, report = run_cleanup(args.root, settings, args.input, args.format, progress)
        else:
            if not args.choices: raise ValueError('Supply the reviewed choices file')
            output, report = apply_choices(args.root, args.choices, progress)
        page = output / ('index.html' if (output / 'index.html').exists() else 'report.html')
        print(f'Results: {page}', flush=True)
        if args.open: webbrowser.open(page.as_uri())
        return 0 if report['status'] == 'MEANING_CHECKS_PASSED_REVIEW_RECOMMENDED' else 2
    except KeyboardInterrupt:
        print('Stopped. Completed source windows and meaning checks are cached for next time.', file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Could not complete: {error}', file=sys.stderr)
        if isinstance(error, (OSError, FileNotFoundError)) and 'model' in str(error).lower():
            print('If a local model is missing, run Download Phase 2 Models.bat once.', file=sys.stderr)
        else:
            print('Completed source analysis is saved. Fix the reported issue and rerun; '
                  'there is no need to download models again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
