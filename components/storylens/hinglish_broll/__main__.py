import argparse
import sys
from pathlib import Path

def run(*args,**kwargs):
    from .pipeline import run as execute
    return execute(*args,**kwargs)


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Add B-roll to a timeline or video. Local AI planning.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', required=True, help='Sequence XML (Premiere/Resolve) or video file/folder')
    parser.add_argument('--format', choices=['instagram_vertical', 'square', 'youtube_horizontal'],
                        help='Canvas for video input (XML input keeps its own sequence size)')
    parser.add_argument('--density', choices=['low', 'medium', 'high'])
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--count',type=int,default=0,help='Desired cutaways; zero uses automatic coverage')
    parser.add_argument('--brief',default='',help='Optional user direction for scene planning')
    parser.add_argument('--reference-script',type=Path,help='Optional script for context; timing still comes from the video')
    parser.add_argument('--black-background', action='store_true', help='Keep speech on black for an audio-only relevance test')
    parser.add_argument('--review-options',action='store_true',help='Collect multiple related videos for human selection')
    parser.add_argument('--options-per-moment',type=int,default=None)
    parser.add_argument('--orientation',choices=['vertical','horizontal'])
    parser.add_argument('--strict-vision-review',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        from .choice_policy import choice_limit
        args.options_per_moment=choice_limit(args.options_per_moment,args.orientation,output_format=args.format)
        from .worker_lease import worker_lease
        with worker_lease(Path(args.root),progress=lambda m:print(m,flush=True)):
            result = run(Path(args.root), Path(args.input), args.format, args.density, args.device,
                         progress=lambda m: print(m, flush=True), black_background=args.black_background,
                         target_count=args.count,brief=args.brief,review_options=args.review_options,
                         options_per_moment=args.options_per_moment,website_review=not args.strict_vision_review,orientation=args.orientation,
                         reference_script=args.reference_script.read_text(encoding='utf-8-sig') if args.reference_script else '')
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
