import json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent.parent
base=root/'output/reference-analysis/cricket-documentaries'
started=time.time()
while not (base/'mi2020/transcript.json').exists():
    if time.time()-started>3600:raise RuntimeError('First video transcription did not complete; resume its saved scan before continuing.')
    time.sleep(2)
items=json.loads((base/'inventory.json').read_text(encoding='utf-8'))
for stage in ('native scan','speech'):
    for item in sorted(items,key=lambda i:i['duration']):
        slug=Path(item['name']).stem.split()[0]
        receipt=base/slug/('scan.json' if stage=='native scan' else 'transcript.json')
        if receipt.exists():continue
        print('PROCESSING ONE SOURCE ('+stage+'): '+item['name'],flush=True)
        args=[sys.executable,'-u',str(root/'tools/analyze_documentary_reference.py'),'--input',item['path'],'--out',str(base/slug),'--root',str(root)]
        if stage=='speech':args.append('--speech-only')
        result=subprocess.run(args,env={**os.environ,'PYTHONPATH':str(root),'DOCUMENTARY_HW_DECODER':'h264_cuvid'})
        if result.returncode:raise RuntimeError('Stopped at '+item['name']+'; completed source receipts are retained.')
print('ALL SEVEN REFERENCE SCANS AND SPEECH PASSES COMPLETE',flush=True)
