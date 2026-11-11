"""Command line shared by the two tools (python -m hinglish_aiimage / python -m hinglish_aivideo)."""
import argparse
import json
import sys
from pathlib import Path

from .pipeline import TOOLS, run
from .settings import SIZES, GenSettings

FORMATS = {'instagram_vertical': '9:16', 'youtube_horizontal': '16:9', 'square': '1:1'}


def main(kind):
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tool = TOOLS[kind][1]
    parser = argparse.ArgumentParser(description=f'{tool}: made locally on your NVIDIA GPU for your script.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', default='', help='Optional: your video or timeline XML (results are placed on it)')
    parser.add_argument('--script', type=Path, help='Your script (.txt)')
    parser.add_argument('--style', default='cinematic', help='cinematic / documentary / 3d / illustration / anime / my:<name>')
    parser.add_argument('--custom-style', default='', help='A one-off style prompt instead of the menu')
    parser.add_argument('--count', default='medium', help='low / medium / high or an exact number')
    parser.add_argument('--options', type=int, default=2 if kind == 'image' else 1,
                        help='Pictures per moment (AI Video: first frames to choose from), 1-4')
    parser.add_argument('--aspect', choices=['auto'] + list(SIZES), default='auto')
    parser.add_argument('--brain', choices=['auto', 'ollama', 'local'], default='auto')
    parser.add_argument('--no-check', action='store_true', help='Do not let the vision model check the results')
    parser.add_argument('--request-mode',choices=['script','idea'],default='script')
    parser.add_argument('--channel',choices=['auto','general','gaming','cricket'],default='auto')
    parser.add_argument('--purpose',choices=['scene','thumbnail','background'],default='scene')
    if kind == 'video':
        parser.add_argument('--video-method',choices=['generative','reference','motion'],default='generative')
        parser.add_argument('--reference',default='')
        parser.add_argument('--motion-style',choices=['gsap','orbit','product','explainer','studio'],default='orbit')
        parser.add_argument('--quality',choices=['full','preview'],default='full')
        parser.add_argument('--from-text', action='store_true', help='Animate from the text only (no first frame)')
    parser.add_argument('--doctor', action='store_true', help='Show whether the GPU and models are ready')
    parser.add_argument('--device', help=argparse.SUPPRESS)
    parser.add_argument('--format', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.doctor:
        from .engine import doctor
        print(json.dumps(doctor(Path(args.root).resolve()), indent=1))
        return 0
    try:
        script = args.script.read_text(encoding='utf-8-sig') if args.script else ''
        image_request={}
        if kind=='image':
            from .direct import decode_request
            script,image_request=decode_request(script)
        aspect = FORMATS.get(args.format, 'auto') if args.aspect == 'auto' else args.aspect
        settings = GenSettings(kind=kind, style=args.style, custom_style=args.custom_style, count=args.count,
                               options=args.options, aspect=aspect, brain=args.brain, check=not args.no_check,
                               from_picture=not getattr(args, 'from_text', False),
                               request_mode=image_request.get('request_mode',args.request_mode),
                               channel=image_request.get('channel',args.channel),purpose=image_request.get('purpose',args.purpose),
                               video_method=getattr(args,'video_method','generative'),reference=getattr(args,'reference',''),
                               motion_style=getattr(args,'motion_style','orbit'),quality=getattr(args,'quality','full'))
        result = run(Path(args.root), args.input or None, script, settings, progress=lambda m: print(m, flush=True))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0
