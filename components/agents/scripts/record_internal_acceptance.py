"""Record the owner's explicit 4 November internal-only acceptance.

This is a source-bound receipt for that answer, not a reusable approval command.
It cannot authorize sending or publication.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from core import config
    config._LOADED = True
    folder = ROOT/'data/real-delivery-acceptance'
    os.environ.update(DATA_DIR=str(folder), DB_URL='sqlite:///'+str(folder/'suite.db'), NOTIFY_CHANNELS='store')
    from core.store import Store
    from core.workflow_service import WorkflowService
    from core.workflow_store import file_hash
    receipt_path = folder/'owner-internal-acceptance.json'
    if receipt_path.exists():
        print('Owner acceptance already recorded; no actions repeated')
        return
    store = Store()
    service = WorkflowService(store)
    result = json.loads((folder/'result.json').read_text())
    integrated = json.loads((folder/'integrated-result.json').read_text())
    sales = service.ledger.get(integrated['sales']['task_id'])
    reviews = []
    for aid in sales['result']['review_ids']:
        row = store.one('SELECT binding_json FROM suite_reviews WHERE approval_id=?', (aid,))
        binding = json.loads(row['binding_json'])
        assert binding['action_type'] == 'prepare'
        assert binding['exact']['payload']['outgoing_authorized'] is False
        reviews.append({'approval_id': aid, 'exact_payload_hash': binding['exact_payload_hash']})
    assert len(reviews) == 5
    video = next(a for a in result['render']['artifacts'] if a['type'] == 'mp4')
    assert file_hash(video['locator']) == video['content_hash']
    receipt = {'recorded_at': datetime.now(timezone.utc).isoformat(),
        'source': 'Owner reply to request_user_input_async call_882894dacc954266a53a3e10dc8ca2c1, item 0',
        'quote': 'Accept for internal acceptance',
        'scope': 'Owner-internal ten-second delivery and five drafts only',
        'delivery_task_id': result['task_id'], 'delivery_revision': result['revision'],
        'artifact': video, 'draft_reviews': reviews,
        'review_document_sha256': file_hash(folder/'OWNER-REVIEW.md'),
        'commercial_client_acceptance': False, 'sending_authorized': False,
        'upload_authorized': False, 'publication_authorized': False,
        'learning_summary_approval_inferred': False}
    for review in reviews:
        row = store.one('SELECT consumed FROM suite_reviews WHERE approval_id=?', (review['approval_id'],))
        if not row['consumed']:
            service.decide(sales['task_id'], True, review['approval_id'])
    delivery = service.ledger.get(result['task_id'])
    service.ledger.update(delivery['task_id'], delivery['state'], {**delivery['result'],
        'owner_internal_acceptance': receipt,
        'verified_result': 'Cortana delivery technically verified and accepted by the owner for internal use; nothing sent'})
    store.event('owner_internal_acceptance', 'client_delivery', delivery['task_id'],
                source=receipt['source'], artifact_hash=video['content_hash'], sending_authorized=False)
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    result['owner_visual_review'] = 'accepted_internal'
    result['owner_acceptance_receipt'] = str(receipt_path)
    (folder/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    integrated['sales']['owner_usefulness_review'] = 'accepted_internal'
    integrated['sales']['review_state'] = service.ledger.get(sales['task_id'])['state']
    (folder/'integrated-result.json').write_text(json.dumps(integrated, indent=2), encoding='utf-8')
    print(json.dumps({'receipt':str(receipt_path),'drafts_reviewed':5,'sent':False,'published':False}))


if __name__ == '__main__':
    main()
