"""Persist the owner's accepted procedure without removing historical guidance."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
file=root/'hinglish_app/knowledge/publishing_workflow.json'
data=json.loads(file.read_text('utf-8-sig'))
identity='broll-approved-parallel-manual-bank-2026-10-29'
text=('LATEST OWNER-APPROVED B-ROLL WORKFLOW, 29 October 2026. This supersedes older '
      'B-roll API/Vision and six-option guidance, which remains preserved historically. '
      'Use videos only and direct website search, no stock API calls and no local Vision gate. '
      'The configured local language model interprets speech and produces relevant keywords '
      'with original word/phrase timestamps. Search all five connected sources: Pexels and '
      'Pixabay through the opt-in Stock Chrome connector, plus Mixkit, Coverr and Videezy '
      'through supported public website adapters. Search independent providers concurrently '
      'with bounded metadata workers and at most two Chrome tabs; download/decode sequentially '
      'for low RAM. Continue with available sources if one fails; do not bypass verification '
      'or treat availability as guaranteed relevance. Ask Vertical / Horizontal before a new run. '
      'Offer at most FIVE videos per highlight for Instagram/vertical and TWO for '
      'YouTube/horizontal, fewer if fewer usable matches exist. Keep native requested orientation; '
      'do not disguise cropped horizontal footage as portrait. Human reviews and selects the '
      'final footage; preserve source links, licence metadata, original media, speech timings, '
      'saved decisions and resumable checkpoints. Do not truncate already approved old banks. '
      'Accepted E3 review: output/broll/20261029-023717-82cf91/001-e3; accepted E2 review: '
      'output/broll/20261029-021804-52d2ed/001-e2-1-. Those videos came from Pexels and Mixkit; '
      'the other connected sites remain eligible. Production runs use local models and tools, '
      'not a required ChatGPT subscription. This is saved procedural memory, not weight training. '
      'Native editor handoff needs its own actual validation; do not claim untested imports work.')
if not any(chunk.get('id')==identity for chunk in data['chunks']):
    data['chunks'].insert(0,{'id':identity,'title':'Approved five-source B-roll search and platform limits',
        'topics':['broll','b-roll','stock footage','videos','website','instagram','youtube','workflow','pexels','pixabay','mixkit','coverr','videezy'], 'text':text})
    data['version']=int(data.get('version',0))+1
    file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
guide=root/'docs/broll-approved-workflow-2026-10-29.md'
guide.write_text('# Approved B-roll workflow — 29 October 2026\n\n'+text+'\n',encoding='utf-8')
queue=root/'docs/broll-reliability-queue-2026-10-28.md'
marker='### Owner-approved five-source workflow — 29 October 2026'
current=queue.read_text('utf-8')
if marker not in current:
    queue.write_text(current+'\n\n'+marker+'\n\n- Preserve all five source connections; current website-only/manual-review workflow accepted.\n- New generations: Instagram/vertical maximum five options, YouTube/horizontal maximum two. Historical reviews preserved.\n- Saved local-model guidance: publishing_workflow.json, newest chunk '+identity+'.\n- [ ] One real new E5 run: D:/Full Drive/thisis.vineet/e5/e5 zomato_chf3_prob3.mov (33.228s, portrait). Show actual review and record elapsed scope.\n- Native website-bank handoff and long-form validation remain separately pending.\n',encoding='utf-8')
print(json.dumps({'saved':identity,'version':data['version'],'source_count':5}))
