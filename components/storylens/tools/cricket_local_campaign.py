"""Run the explicitly requested 19 October cricket campaign, with saved decisions."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hinglish_cut.model_storage import configure
configure(ROOT)
from hinglish_publish.campaign import prepare, upload_private, review, quality, refine, verify_schedule, word_refine, finish_copy

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','refine','review','quality','finalize','word-finalize','repair-final','copy','upload','verify'])
    args=parser.parse_args()
    folder=ROOT/'output/campaigns/cricket-20261019'
    if args.action=='prepare':
        prepare(ROOT,r'D:\Editing\documentry edit\final videos\final videos',folder,
                progress=lambda s:print(s,flush=True))
    elif args.action=='copy':
        finish_copy(ROOT,folder,progress=lambda s:print(s,flush=True))
    elif args.action=='repair-final':
        word_refine(ROOT,folder,progress=lambda s:print(s,flush=True),indexes=[5])
        review(ROOT,folder,progress=lambda s:print(s,flush=True))
        quality(folder)
    elif args.action=='word-finalize':
        word_refine(ROOT,folder,progress=lambda s:print(s,flush=True))
        review(ROOT,folder,progress=lambda s:print(s,flush=True))
        quality(folder)
    elif args.action=='finalize':
        refine(ROOT,folder,progress=lambda s:print(s,flush=True))
        review(ROOT,folder,progress=lambda s:print(s,flush=True))
        quality(folder)
    elif args.action=='refine':
        refine(ROOT,folder,progress=lambda s:print(s,flush=True))
    elif args.action=='review':
        review(ROOT,folder,progress=lambda s:print(s,flush=True))
    elif args.action=='quality':
        quality(folder)
    elif args.action=='verify':
        verify_schedule(ROOT,folder)
    else:
        upload_private(ROOT,folder,progress=lambda s:print(s,flush=True))
