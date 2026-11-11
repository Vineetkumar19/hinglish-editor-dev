"""Explicit read-only YouTube checks alongside an independent Instagram run."""
import re
import time


def requested(text):
    return bool(re.search(r'\b(?:youtube|yt)\s*[:,-]?\s+(?:check|validate|verify)[ -]only\b',text,re.I))


def run(assistant,session_id,review):
    from hinglish_publish.providers import youtube_client
    from hinglish_publish.metadata import validate
    from hinglish_publish.store import fingerprint
    from .assistant_copy_review import ensure
    checked=[]
    for profile,account in review['accounts'].items():
        client,stored=youtube_client(assistant.root,profile)
        channels=client.channels().list(part='snippet',mine=True).execute().get('items',[])
        if stored['channel_id']!=account['id'] or len(channels)!=1 or channels[0]['id']!=account['id']:
            raise ValueError('The live YouTube channel does not match the reviewed destination.')
        for row in review['rows']:
            if row['profile']!=profile:continue
            job=ensure(assistant,session_id,review,assistant.state.publisher.store.get(row['id']))
            validate(job['metadata'])
            if fingerprint(job['video'])!=job['fingerprint']:
                raise ValueError('The YouTube draft export changed.')
            checked.append({'id':job['id'],'channel_id':account['id'],'title':job['metadata']['title'],
                            'checked_at':time.time(),'upload_attempted':False})
    review['youtube_checks']=checked
    assistant._update(session_id,publishing_review=review)
    assistant._message(session_id,'assistant',
        f'YouTube check only: live channel connection and {len(checked)} local video drafts validated. '
        'No upload or schedule was sent. Upload-limit availability cannot be confirmed by this read-only check.',
        youtube_checks=checked)
