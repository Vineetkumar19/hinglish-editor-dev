"""Run several Earshot acoustic rankings in one warm CPU process."""
import json
from pathlib import Path
import sys


def main(inp,out):
    from earshot import api
    request=json.loads(Path(inp).read_text(encoding='utf-8'))
    rows=[]
    for slate in request.get('slates',[])[:8]:
        paths=[p for p in slate.get('paths',[])[:6] if Path(p).is_file()]
        if not paths:continue
        try:
            ranked=api.rank(paths,str(slate.get('query',''))[:160],top=len(paths))
            rows.append({'moment':slate['moment'],'query':slate['query'],
                         'results':ranked.get('results',[])})
        except (OSError,ValueError,RuntimeError):
            rows.append({'moment':slate['moment'],'query':slate['query'],'results':[]})
    Path(out).write_text(json.dumps({'tool':'earshot','slates':rows},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
