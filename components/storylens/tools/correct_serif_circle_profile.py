"""Migrate only Serif Circle; preserve the owner-approved profile in evidence."""
import json
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    path=ROOT/'hinglish_captions/serif_circle_reference.json'
    cfg=json.loads(path.read_text('utf8'))
    cfg['pattern_contract']={'script_changes':'Only words and timing change; retain the source pattern, fonts, hierarchy, colors, accents and motion.',
                             'pagination':'Continue longer scripts across pages using the same frozen source pattern. Never fall back to generic plain text.',
                             'reveal':'Reserve complete word slots before reveal; keep revealed words fixed.',
                             'owner_edits':'Retain subsequent positioning and size edits through saving.'}
    for index in (3,15):
        if index<len(cfg['recipes']):
            for row in cfg['recipes'][index]['rows']:row['case']='upper'
    if cfg.get('revision',0)>=4:
        for recipe in cfg['recipes']:
            for row in recipe['rows']:
                row['role']='emphasis' if row.get('face')=='serif' else 'support'
        path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n','utf8')
        return
    recipes=cfg['recipes']
    # The measured English review already contains the source's open sweeps.
    # Use those contours for the Portuguese originals too, instead of ellipses.
    for source,target in ((12,0),(14,2),(15,3),(16,5),(18,6)):
        recipes[target]['decorations']=deepcopy(recipes[source]['decorations'])
        if target==0:recipes[target]['decorations'][0]['trigger']=3
        if target==6:recipes[target]['decorations'][0]['trigger']=2
    bands={0:[0,1,2,3],5:[0,0,1,2],6:[0,0,1,2],11:[0,0],16:[0,0,1,2],18:[0,0,1,2]}
    targets={0:[2,3],2:[2,3],3:[0,1,2],5:[2,3],6:[0,1,2,3],12:[2,3],14:[2,3],15:[0,1,2],16:[2,3],18:[0,1,2,3]}
    # Measured delays: source green starts with unico; red begins ~.20s
    # after the first header; underlines start ~.10s after the serif word.
    for i,r in enumerate(recipes):
        r['reference_pattern']=i<12
        for j,row in enumerate(r['rows']):
            row.update(source_row=j,band=bands.get(i,list(range(len(r['rows']))))[j],reveal='row',role='emphasis' if row.get('face')=='serif' else 'support')
        for d in r.get('decorations',[]):
            d['target_rows']=targets[i]
            d['linear']=True
            if d['kind']=='circle':
                d['duration']=.45 if i in (0,12) else .60
                d['delay']=0 if i in (0,12) else .20
            else:d.update(duration=.60,delay=.10,taper=True)
    # The replacement cut stays at one location; its second word must not
    # acquire a new row just because the script was edited.
    recipes[4]['rows'][1]['band']=0
    cfg.update(revision=4,status='correction_pending_owner_review',
        layout={'max_row_width':600,'min_ink_gap':3,'max_ink_gap':8,'anchor':[.5,.65]},
        correction={'date':'2026-10-23','request':'Restore reference contours, staggered ink alignment and motion; retain patterns through script changes.',
                    'previous_profile':'output/captions/serif-circle-correction/before-profile.json',
                    'application_validation':'Owner performs Storylens and Premiere testing; not run by Codex.'})
    path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n','utf8')

if __name__=='__main__':main()
