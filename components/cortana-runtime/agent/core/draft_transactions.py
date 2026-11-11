"""Single-version draft approvals; native send adapters must prove live identity.

Existing adapters remain manual-send-only until their sender, live-composer and
send-reconciliation capabilities have passed native acceptance.
"""
import hashlib
import json
import time
from core import local_store as store


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def _validated(payload):
    required = {'platform','sender_account_id','recipient_id','body','subject','attachment_hashes','cc','bcc'}
    if set(payload) != required:
        raise ValueError('A review needs platform, sender, recipient, body, subject, CC/BCC and attachment hashes.')
    if payload['platform'] not in {'whatsapp','instagram','telegram','gmail'}:
        raise ValueError('Unsupported draft platform.')
    if not all(isinstance(payload[k],str) for k in ('platform','sender_account_id','recipient_id','body','subject')):
        raise ValueError('Draft text and identities must be strings.')
    if not payload['sender_account_id'] or not payload['recipient_id'] or not payload['body']:
        raise ValueError('Resolve the exact sender and recipient before review.')
    if not all(isinstance(payload[k],list) and all(isinstance(x,str) for x in payload[k]) for k in ('attachment_hashes','cc','bcc')):
        raise ValueError('Attachment hashes, CC and BCC must be explicit lists.')
    return {'payload':payload,'content_hash':payload_hash(payload),'status':'READY_FOR_REVIEW',
        'created_at':time.time(),'send_capability':'manual_only_until_adapter_acceptance'}


def prepare(payload):
    return store.put('draft', _validated(payload))


def edit(draft_id, payload):
    previous = store.get('draft',draft_id)
    if previous['status'] in {'SENDING','SENT','UNCERTAIN'}:
        raise ValueError('Reconcile the previous send before changing this transaction.')
    updated = _validated(payload)
    updated.pop('approval',None)
    updated['status']='EDITED'
    return store.put('draft',updated,draft_id,previous['revision'])


def approve(draft_id, revision, content_hash, approver='owner', ttl=120):
    draft = store.get('draft',draft_id)
    if draft['revision'] != revision or draft['content_hash'] != content_hash or draft['status'] not in {'READY_FOR_REVIEW','EDITED'}:
        raise ValueError('Draft changed or is not ready for review.')
    now=time.time()
    draft['status']='APPROVED'
    draft['approval']={'draft_id':draft_id,'content_hash':content_hash,'sender_account_id':draft['payload']['sender_account_id'],
        'recipient_id':draft['payload']['recipient_id'],'subject':draft['payload']['subject'],
        'attachment_hashes':draft['payload']['attachment_hashes'],'approver':approver,'approval_time':now,
        'expires_at':now+min(120,max(1,ttl)),'consumed':False}
    return store.put('draft',draft,draft_id,revision)


def cancel(draft_id):
    draft=store.get('draft',draft_id)
    if draft['status'] in {'SENT','SENDING','UNCERTAIN'}:
        raise ValueError('An in-flight or observed send cannot be undone. Reconcile it first.')
    draft.update(status='CANCELLED');draft.pop('approval',None)
    return store.put('draft',draft,draft_id,draft['revision'])


def revoke_all():
    count=0
    with store.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows=conn.execute("SELECT data FROM records WHERE kind='draft'").fetchall()
        for row in rows:
            draft=json.loads(row['data'])
            if draft['status']=='APPROVED':
                draft.update(status='READY_FOR_REVIEW');draft.pop('approval',None)
                store.put_in_transaction(conn,'draft',draft,draft['id'],draft['revision'])
                count+=1
    return count


def send_approved(draft_id, adapter):
    """No model tool gets an arbitrary adapter or bypasses its capability gate."""
    from core.tasks import check_cancelled
    from core.tool_registry import serialized_effects
    with serialized_effects():
        draft=store.get('draft',draft_id)
        approval=draft.get('approval',{})
        if draft['status']!='APPROVED' or approval.get('consumed') or approval.get('expires_at',0)<time.time():
            raise ValueError('Approval missing, expired, consumed, or invalidated.')
        if not getattr(adapter,'send_acceptance_verified',False):
            raise ValueError('This adapter is manual-send-only; native sender/composer/send verification is not accepted.')
        check_cancelled()
        observed=adapter.observe(draft)
        if observed.get('externally_sent'):
            draft.update(status='SENT' if observed.get('verified') else 'UNCERTAIN',evidence=observed)
            draft.pop('approval',None)
            return store.put('draft',draft,draft_id,draft['revision'])
        if payload_hash(observed['payload'])!=approval['content_hash']:
            draft.update(status='EDITED');draft.pop('approval',None)
            store.put('draft',draft,draft_id,draft['revision'])
            raise ValueError('The live sender, recipient, text or attachments changed. Review again.')
        check_cancelled()
        if approval['expires_at'] < time.time():
            draft.update(status='READY_FOR_REVIEW');draft.pop('approval',None)
            store.put('draft',draft,draft_id,draft['revision'])
            raise ValueError('Approval expired while checking the live composer. Review again.')
        approval['consumed']=True
        draft['status']='SENDING'
        draft=store.put('draft',draft,draft_id,draft['revision'])
        try:
            adapter.send_once(draft)
            evidence=adapter.verify_send(draft)
            draft.update(status='SENT' if evidence.get('verified') else 'UNCERTAIN',evidence=evidence)
        except BaseException:
            draft.update(status='UNCERTAIN',evidence={'note':'Outcome unknown; do not retry automatically.'})
            store.put('draft',draft,draft_id,draft['revision'])
            raise
        return store.put('draft',draft,draft_id,draft['revision'])
