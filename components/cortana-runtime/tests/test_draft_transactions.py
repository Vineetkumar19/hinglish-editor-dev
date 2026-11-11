import time
from types import SimpleNamespace
import pytest
from core import draft_transactions as drafts, local_store as store


def payload(platform='gmail',suffix=''):
    return {'platform':platform,'sender_account_id':'owner@example.com','recipient_id':'demo@example.com',
            'body':'Fictional unsent test '+suffix,'subject':'Demo','attachment_hashes':[],'cc':[],'bcc':[]}


@pytest.mark.parametrize('platform', ['gmail','whatsapp','instagram','telegram'])
@pytest.mark.parametrize('variant',['plain','with quote "send it"','with URL https://example.com','line\nbreak','unicode punctuation —'])
def test_twenty_drafts_never_invoke_a_send(platform,variant):
    result=drafts.prepare(payload(platform,variant))
    assert result['status']=='READY_FOR_REVIEW'
    assert result['send_capability'].startswith('manual_only')
    assert 'approval' not in result


@pytest.mark.parametrize('change', ['sender_account_id','recipient_id','body','subject','attachment_hashes','cc','bcc'])
def test_live_change_invalidates_approval(change):
    item=drafts.prepare(payload())
    approved=drafts.approve(item['id'],item['revision'],item['content_hash'])
    changed=payload()
    changed[change]=['different'] if isinstance(changed[change],list) else 'different'
    adapter=SimpleNamespace(send_acceptance_verified=True,observe=lambda _: {'payload':changed},
                            send_once=lambda _:pytest.fail('Changed draft was sent'))
    with pytest.raises(ValueError,match='changed'):
        drafts.send_approved(item['id'],adapter)
    assert store.get('draft',item['id'])['status']=='EDITED'


def test_expired_approval_cannot_send():
    item=drafts.prepare(payload());item=drafts.approve(item['id'],item['revision'],item['content_hash'])
    item['approval']['expires_at']=time.time()-1;store.put('draft',item,item['id'],item['revision'])
    with pytest.raises(ValueError,match='expired'):
        drafts.send_approved(item['id'],SimpleNamespace())


def test_uncertain_send_is_never_replayed():
    item=drafts.prepare(payload());drafts.approve(item['id'],item['revision'],item['content_hash'])
    calls=[]
    def unknown(_):
        calls.append(1);raise TimeoutError('Test timeout')
    adapter=SimpleNamespace(send_acceptance_verified=True,observe=lambda _:{'payload':payload()},send_once=unknown)
    with pytest.raises(TimeoutError):drafts.send_approved(item['id'],adapter)
    assert store.get('draft',item['id'])['status']=='UNCERTAIN'
    with pytest.raises(ValueError):drafts.send_approved(item['id'],adapter)
    assert calls==[1]


def test_manual_send_is_reconciled_without_another_send():
    item=drafts.prepare(payload());drafts.approve(item['id'],item['revision'],item['content_hash'])
    adapter=SimpleNamespace(send_acceptance_verified=True,observe=lambda _:{'externally_sent':True,'verified':True},
                            send_once=lambda _:pytest.fail('Duplicate send'))
    assert drafts.send_approved(item['id'],adapter)['status']=='SENT'


def test_unaccepted_adapter_cannot_use_approval():
    item=drafts.prepare(payload());drafts.approve(item['id'],item['revision'],item['content_hash'])
    with pytest.raises(ValueError,match='manual-send-only'):
        drafts.send_approved(item['id'],SimpleNamespace())
