"""Assistant-owned read-only reconciliation after an uncertain Instagram Share."""
import re


def followup(assistant,session_id,text,snapshot):
    if not (re.match(r'^\s*(?:please\s+)?(?:verify|check|confirm)\b',text,re.I)
            and re.search(r'\bInstagram\b',text,re.I)
            and re.search(r'\b(?:publication|published|receipt|existing post)\b',text,re.I)):
        return False
    review=snapshot.get('publishing_review') or {}
    rows=review.get('instagram_rows',[])
    if not rows:return False
    bridge=assistant.state.local_browser
    uncertain=[]
    for row in rows:
        if not row.get('browser_job_id'):continue
        job=bridge.get(row['browser_job_id'])
        if job['status']=='needs_review' and job.get('submission_started'):
            uncertain.append(job)
    if not uncertain:return False
    jobs=[bridge.verify_publication(j['id']) for j in uncertain]
    from .assistant_pipeline import change
    change(assistant,session_id,phase='waiting_instagram')
    assistant._message(session_id,'assistant',
        f'{len(jobs)} read-only Instagram receipt check queued. I will inspect the existing post’s account, '
        'exact caption and publication time. No video will be uploaded again. '
        'Leave the destination profile or published post open in Chrome.')
    assistant._update(session_id,status='complete',stage='Waiting for the local extension to verify the existing Instagram post.')
    return True
