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
    parser.add_argument('--content-form', choices=['auto','short','long'])
    parser.add_argument('--no-music', action='store_true')
    parser.add_argument('--no-effects', action='store_true')
    parser.add_argument('--no-transitions', action='store_true')
    parser.add_argument('--restrained', action='store_true', help='Use the previous sparse single-event planner')
    audio=parser.add_mutually_exclusive_group()
    audio.add_argument('--remove-source-music',dest='remove_source_music',action='store_true')
    audio.add_argument('--keep-source-audio',dest='remove_source_music',action='store_false')
    parser.set_defaults(remove_source_music=None)
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--script', type=Path, help='Your script (.txt): fixes misheard names and gives the AI context')
    parser.add_argument('--refresh-export',type=Path,help='Rebuild an existing saved sound plan without changing choices or recording owner feedback')
    args = parser.parse_args()
    overrides = {'style': args.style, 'density': args.density, 'device': args.device,'content_form':args.content_form,
                 'music': False if args.no_music else None, 'effects': False if args.no_effects else None,
                 'transitions': False if args.no_transitions else None,
                 'layered': False if args.restrained else None,'remove_source_music':args.remove_source_music}
    try:
        if args.refresh_export:
            import json
            from .pipeline import remix
            root=Path(args.root).resolve();plan=args.refresh_export.resolve()
            if not plan.is_relative_to(root/'output/sound') or plan.name!='sound-plan.json':raise ValueError('Choose a saved Sound Design plan inside this project.')
            data=json.loads(plan.read_text('utf-8'))
            keep=data.get('kept',list(range(len(data.get('all_cues') or data['cues']))))
            remix(plan,keep,bool(data.get('music')),progress=lambda m:print(m,flush=True),remember_choices=False)
            result=plan.parent/'report.html'
        else:
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
