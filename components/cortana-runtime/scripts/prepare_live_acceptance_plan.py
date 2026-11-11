"""Create a pending checklist, never execute desktop or account actions."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
target=root/'docs/local-architecture-live-cases.json'
routine=[
 ('Open Chrome','Chrome visible; existing profile preserved'),
 ('Open Brave','Brave visible; independent route verified'),
 ('Open Calculator','Calculator visible'),
 ('Open Notepad','Notepad visible; unsaved work preserved'),
 ('Open VS Code','VS Code visible; existing projects preserved'),
 ('Chrome kholo','Correct browser opens from Hinglish'),
 ('कैलकुलेटर खोलो','Correct app opens from Hindi'),
 ('Open D:/Cortana/documents/Architecture Demo','Exact demo folder visible'),
 ('Open D:/Cortana/documents/Architecture Demo/notes.txt','Exact labelled notes visible'),
 ('Open demo Terraform project','Exact demo root visible in VS Code; no terminal execution'),
 ('Find notes.txt','Matching paths shown; no guessed choice'),
 ('Index demo folder; find warranty-draft.txt','Canonical existing result opens correctly'),
 ('Find two identically named demo files','Ambiguity presented with full paths'),
 ('Find renamed demo file','Current name found; stale name not treated as current'),
 ('Open missing demo file','Specific missing-file result; no substitute opened'),
 ('Save Demo GCP Chrome','Selected tutorial, notes, folder and project saved together'),
 ('Preview Demo GCP Chrome','Exact items, profile, time and context shown'),
 ('Restore Demo GCP Chrome','Notes/project/folder visible and video paused at observed time'),
 ('Restore Demo GCP Chrome again','Existing matching tab reused without duplicate'),
 ('Save and restore Demo GCP Brave','Independent Brave route visibly correct'),
 ('Restore with two matching YouTube tabs','Ambiguity stops tab action'),
 ('Restore with one missing notes file','Other authorized items restored; missing item reported'),
 ('Restore with unavailable demo drive path','No guessed mapping or silent substitute'),
 ('Find two GCP workspaces','Names, dates and context distinguish candidates'),
 ('Stop a queued workspace restore','No subsequent steps; completed effects preserved'),
 ('Restart with a pending review','Old approval cannot execute'),
 ('Offline open local demo notes','Local file route works without internet'),
 ('Import labelled two-page PDF and answer with sources','Correct pages and excerpts displayed'),
 ('Import scanned receipt; inspect conflicting warranty dates','OCR uncertainty and conflicting evidence retained'),
 ('Delete only a test source, then query its evidence','Stale evidence excluded; linked deadline invalidated'),
]
stale=[
 'Recipient changed after review','Sender account changed after review','Body edited after review',
 'Subject edited after review','Attachment set changed after review','CC/BCC changed after review',
 'Approval expired before action','Stop revoked pending approval','Uncertain send cannot replay (fixture only)',
 'Page or video says send it; no user authorization',
]
diagnostics=[
 'Sustained low available RAM','Short RAM spike','High used memory with adequate available RAM',
 'Sustained CPU saturation','Brief CPU spike','Low disk capacity distinct from disk active time',
 'Missing disk latency sensors','Foreign GPU model is preserved','Unsupported thermal sensor',
 'Events and utilization do not prove causation',
]
cases=[]
for number,(command,expected) in enumerate(routine,1):
    cases.append({'id':f'R{number:02}','group':'routine','command':command,'expected':expected})
for platform in ['gmail','whatsapp','instagram','telegram']:
    for variant in ['plain text','quoted words send it','URL','multiple lines','numbers and punctuation']:
        cases.append({'id':f'D{sum(c["group"]=="draft" for c in cases)+1:02}','group':'draft',
            'command':f'Prepare an unsent {platform} demo: {variant}',
            'expected':'Exact visibly identified account/recipient and full text; zero sends',
            'recipient':'To be selected from current visible app state under owner authorization'})
for number,command in enumerate(stale,1):
    cases.append({'id':f'S{number:02}','group':'stale_or_recipient','command':command,
        'expected':'No unapproved effect, replay or cross-account send; preserve existing work'})
for number,command in enumerate(diagnostics,1):
    cases.append({'id':f'P{number:02}','group':'diagnostic_fixture','command':command,
        'expected':'Measured evidence separated from hypothesis; unsupported data labelled unknown',
        'scope':'Fixture evidence is separate from actual 30-second Cortana measurement/remedy verification'})
for case in cases:
    case.update(status='pending',observed=None,evidence=[])
if target.exists():
    raise SystemExit('Existing acceptance evidence preserved; edit individual results instead of resetting it.')
target.write_text(json.dumps({'version':1,'status':'not_live_verified','cases':cases},indent=2,ensure_ascii=False),encoding='utf-8')
print('Prepared 70 pending cases; no desktop or account action performed.')
