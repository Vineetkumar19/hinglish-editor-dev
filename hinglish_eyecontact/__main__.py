import argparse
import sys
from pathlib import Path

from .maxine import doctor
from .pipeline import run
from .settings import EYE_SIZE, REACH, EyeSettings


def main():
    if hasattr(sys.stdout, 'reconfigure'):   # Windows consoles/pipes default to cp1252
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Eye Contact: look into the camera while reading a script '
                                                 '(NVIDIA Maxine, RTX GPUs).')
    parser.add_argument('--root', default='.')
    parser.add_argument('--input', help='Sequence XML (Premiere/Resolve) or video file/folder')
    parser.add_argument('--doctor', action='store_true', help='Check the GPU and the NVIDIA install, then exit')
    parser.add_argument('--reach', choices=list(REACH), default='near',
                        help='near = script right under the lens; far = paper on the desk / screen to the side')
    parser.add_argument('--no-look-away', action='store_true', help='No natural glances away (can look like staring)')
    parser.add_argument('--eye-size', type=int, choices=list(EYE_SIZE), default=3)
    parser.add_argument('--quality', type=int, default=17, help=argparse.SUPPRESS)
    parser.add_argument('--simulate', action='store_true', help=argparse.SUPPRESS)   # developer pipeline test
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda', help=argparse.SUPPRESS)
    parser.add_argument('--format', help=argparse.SUPPRESS)   # the app sends it; eye contact never reframes
    args = parser.parse_args()
    if args.doctor:
        report = doctor(Path(args.root))
        print(report.text(), flush=True)
        return 0 if report.ready else 1
    if not args.input:
        parser.error('--input is required')
    settings = EyeSettings(args.reach, not args.no_look_away, args.eye_size, args.quality)
    try:
        result = run(Path(args.root), Path(args.input), settings, progress=lambda m: print(m, flush=True),
                     simulate=args.simulate)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f'Error: {error}', flush=True)
        return 1
    print(f'Results: {result}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
