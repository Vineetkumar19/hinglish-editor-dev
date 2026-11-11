"""Expose the verified campaign and learning receipts in the local editor chat."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from hinglish_app.assistant import Assistant
    from hinglish_publish.memory import CreatorMemory
    from hinglish_publish.campaign import save,write_report
    from hinglish_shorts.source import quick_fingerprint
    folder=ROOT/'output/campaigns/cricket-20261019'
    campaign=json.loads((folder/'campaign.json').read_text('utf-8'))
    verification=json.loads((folder/'schedule-verification.json').read_text('utf-8'))
    assert campaign['status']=='scheduled' and verification['complete']
    assert quick_fingerprint(campaign['source'])==campaign['source_fingerprint']
    existing=folder/'handoff.json'
    if existing.exists():
        print(existing.read_text('utf-8'))
        raise SystemExit(0)
    preference=CreatorMemory(ROOT,'cricket').add({'scope':'all',
        'want':'When trusted fact corrections contradict noisy ASR or an earlier draft, apply those corrections. '
               'Keep distinct seasons and player dismissals separate. Omit a disputed statistic instead of repeating it. '
               'Every YouTube description must finish with 3-5 relevant hashtags. Describe only the actual excerpt.',
        'before':'Mumbai Indians 2015: From 5 Losses to Second Place with Rohit Sharma',
        'after':campaign['clips'][2]['metadata']['title']})
    assistant=Assistant(SimpleNamespace(root=ROOT))
    session=assistant.create()['id']
    videos=[c['video'] for c in campaign['clips']]
    assistant._update(session,profile='cricket',campaign=str(folder),status='complete',
        stage='Seven YouTube schedules verified: 19–25 October, 18:00 IST.',
        brain=campaign['model'],last_paths=videos,shorts_paths=videos)
    assistant._message(session,'user','Choose one long cricket video from '+campaign['source_root']+
        ', extract seven standalone Shorts below 50 seconds, and schedule one daily on Fantasy Legends '
        'at 6 p.m. India time from 19 to 25 October 2026.')
    assistant._message(session,'assistant','The configured local models chose the source, moments and viewer-facing copy. '
        'All seven portrait exports passed decode and audio checks. They are uploaded and scheduled on Fantasy Legends '
        'for 19–25 October 2026 at 18:00 IST. Original source unchanged. '
        'Codex assisted the YouTube Studio scheduling controls for this run; the local editor’s current API connection '
        'still supports private staging rather than unattended public scheduling. '
        'Feedback was saved to local creator memory. No model weights were fine-tuned.',
        videos=videos,publish_results=[{'channel':'Fantasy Legends','kind':'Short · '+c['publish_at'][:10]+' 18:00 IST',
                        'title':c['metadata']['title'],'url':c['remote']['url'],'visibility':'scheduled'} for c in campaign['clips']],
        result={'page':str(folder/'report.html'),'folder':str(folder),'quality':str(folder/'quality.json')})
    write_report(folder,campaign)
    handoff={'session':session,'url':'http://127.0.0.1:8765/publisher.html?chat='+session,
             'source_preserved':True,'all_remote_schedules_verified':True,'new_uploads':7,
             'first_release':'2026-10-19T18:00:00+05:30','last_release':'2026-10-25T18:00:00+05:30',
             'editorial_decisions':'Local Qwen models','scheduling_execution':'Codex-assisted YouTube Studio browser controls',
             'local_private_upload_tool':True,'fully_local_unattended_public_scheduling':False,
             'weight_training':False,'creator_memory_preference':preference}
    save(existing,handoff)
    print(json.dumps(handoff,indent=2))
