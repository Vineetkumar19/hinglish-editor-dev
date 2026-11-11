"""python -m hinglish_motion: motion graphics for your script or video, rendered on this PC."""
import argparse
import json
import sys
from pathlib import Path

from .settings import SIZES, MotionSettings

FORMATS = {'instagram_vertical': '9:16', 'youtube_horizontal': '16:9', 'square': '1:1'}


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Motion Graphics: animated key moments for your documentary edit.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', default='', help='Your video or timeline XML (graphics are placed on it)')
    parser.add_argument('--script', type=Path, help='Your script (.txt)')
    parser.add_argument('--style', default='theme:studio', help='theme:studio for connected assets/GSAP/ThreeUI, another theme, or card:<id>')
    parser.add_argument('--count', default='medium', help='low / medium / high or an exact number')
    parser.add_argument('--mode', choices=['auto', 'full', 'overlay'], default='auto')
    parser.add_argument('--coverage', choices=['auto', 'full', 'key'], default='auto',
                        help='full: the whole script as motion graphics (MOTION_GRAPHICS.mp4); key: key moments only '
                             '(auto: full for a script or a video up to 3 minutes)')
    parser.add_argument('--assets', choices=['all', 'web', 'ai'], default='all',
                        help='where pictures come from: all (web + Pexels/Pixabay + AI Images), web, or ai objects')
    parser.add_argument('--no-check', action='store_true', help='Do not let the vision model check the pictures')
    parser.add_argument('--aspect', choices=['auto'] + list(SIZES), default='auto', help='Script only: the video shape')
    parser.add_argument('--brain', choices=['auto', 'ollama', 'local'], default='auto')
    parser.add_argument('--quality', choices=['full', 'preview'], default='full')
    parser.add_argument('--engine', choices=['remotion', 'motion-canvas', 'hyperframes'], default='hyperframes')
    parser.add_argument('--compare-script-image',type=Path)
    parser.add_argument('--compare-seconds',type=float,default=50)
    parser.add_argument('--compare-correction',type=Path)
    parser.add_argument('--object-motion-script',type=Path)
    parser.add_argument('--object-motion-continue',type=Path)
    parser.add_argument('--reference', type=Path, help='Analyze one reference and locally author new layers and sound')
    parser.add_argument('--sounds-folder', default='', help='Additional owner-supplied sound pack folder')
    parser.add_argument('--brain-model', default='qwen3:8b', help='Installed Ollama model name; documentary memory remains in the project')
    parser.add_argument('--styles', action='store_true', help='List the themes and your style cards')
    parser.add_argument('--learn-style', nargs='+', type=Path, help='Pictures / videos / a folder of a look to learn')
    parser.add_argument('--name', default='', help='Name for --learn-style')
    parser.add_argument('--approve', help='Approve a style card (card_...) so it can be used')
    parser.add_argument('--delete-style', help='Delete a style card')
    parser.add_argument('--device', help=argparse.SUPPRESS)
    parser.add_argument('--format', help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    say = lambda m: print(m, flush=True)
    try:
        from . import style
        if args.styles:
            print(json.dumps([{'value': v, 'name': n} for v, n in style.choices(root)] +
                             [{'card': c.id, 'name': c.name, 'status': c.status} for c in style.load_cards(root)
                              if c.status != 'approved'], indent=1, ensure_ascii=False))
            return 0
        if args.learn_style:
            files = []
            for p in args.learn_style:
                files += style.references_in(p) if p.is_dir() else [p]
            c = style.analyse(root, files, args.name, say)
            say(f'Style card {c.id} "{c.name}" made (candidate). Approve it with --approve {c.id}')
            return 0
        if args.approve:
            c = style.approve(root, args.approve)
            say(f'Approved: {c.name}')
            return 0
        if args.delete_style:
            style.delete(root, args.delete_style)
            say('Deleted')
            return 0
        from .pipeline import run
        aspect = FORMATS.get(args.format, 'auto') if args.aspect == 'auto' else args.aspect
        settings = MotionSettings(count=args.count, style=args.style, mode=args.mode, coverage=args.coverage,
                                  aspect=aspect, assets=args.assets, check=not args.no_check, brain=args.brain,brain_model=args.brain_model,
                                  quality=args.quality, engine=args.engine)
        script = args.script.read_text(encoding='utf-8-sig') if args.script else ''
        if args.object_motion_continue:
            from .object_recovery import run as continue_objects
            result=continue_objects(root,args.object_motion_continue,say)
        elif args.object_motion_script:
            from .object_film import run as object_run
            result=object_run(root,args.object_motion_script,say)
        elif args.compare_script_image:
            from .comparison import run as compare_run
            result=compare_run(root,args.compare_script_image,args.compare_seconds,say,correction_from=args.compare_correction)
        elif args.reference:
            if args.engine != 'hyperframes':
                raise ValueError('Motion engine input unavailable: the reference-copy workflow currently uses Hyperframes. Choose Hyperframes for this reference, or provide a script for Remotion / Motion Canvas.')
            from .reference_run import run as reference_run
            result = reference_run(root,args.reference,script,args.sounds_folder,args.quality,progress=say)
        else:
            result = run(root, args.input or None, script, settings, progress=say)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
