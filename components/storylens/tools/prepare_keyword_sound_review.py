"""Upgrade a saved review using Qwen's keywords; leave its video and timeline choices intact."""
import json
from pathlib import Path
from hinglish_sound.brain import Brain
from hinglish_sound.settings import load_settings
from hinglish_sound.keyword_folders import label_keywords,organize,premiere_project,curate_folders
from hinglish_sound.report import write_report

root=Path(__file__).resolve().parents[1]
folder=root/'output/sound/20261030-155724-cc84d2/002-human-sound-review'
path=folder/'sound-plan.json'
plan=json.loads(path.read_text('utf-8'))
evidence=root/'output/sound-keyword-folder-validation';evidence.mkdir(exist_ok=True)
backup=evidence/'before-keyword-folders.json'
if not backup.exists():backup.write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
settings=load_settings(root)
brain=Brain(root,settings.think_model,settings.embed_model,progress=lambda s:print(s,flush=True))
labels=evidence/'model-keywords.json'
if labels.exists():
    saved=json.loads(labels.read_text('utf-8'))
    for event in plan['human_review']['events']:event['keyword']=saved['keywords'][event['id']]
else:
    label_keywords(brain,plan['human_review']['events'])
    labels.write_text(json.dumps({'model':brain.model,'source':'Saved local Vision/Qwen intents; no new video analysis',
        'keywords':{e['id']:e['keyword'] for e in plan['human_review']['events']}},indent=2),encoding='utf-8')
organize(plan['human_review'])
curated=evidence/'model-folder-options.json'
if curated.exists():plan['human_review']=json.loads(curated.read_text('utf-8'))
else:
    curate_folders(brain,plan['human_review'])
    curated.write_text(json.dumps(plan['human_review'],ensure_ascii=False,indent=2),encoding='utf-8')
plan['content_form']='short'
path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print('Preparing keyword folders and Premiere project',flush=True)
premiere_project(path)
write_report(folder/'report.html',plan['name'],plan,plan.get('preview'))
print(json.dumps({'folders':[(g['name'],len(g['candidates'])) for g in plan['human_review']['folders']],
                  'cues_unchanged':plan['cues']==json.loads(backup.read_text('utf-8'))['cues']}),flush=True)
