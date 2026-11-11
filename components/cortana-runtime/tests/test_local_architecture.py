"""Behavioral contracts, supplementary to the mandatory native acceptance run."""
import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch
import pytest

from core import personal_documents as docs, local_store as store, workspaces, diagnostics, tasks
from core.tool_registry import ToolNeedsConfirmation, dispatch, execute_confirmed
from core.tools_loader import load_all_tools


@pytest.fixture
def selected(tmp_path, monkeypatch):
    source = tmp_path / 'warranty.txt'
    source.write_text('DEMO receipt only. Payment on 2026-11-04. Warranty coverage is not confirmed.\nReview expiry 2026-12-01.', encoding='utf-8')
    monkeypatch.setattr('tools.documents.approved_search_roots', lambda:[str(tmp_path)])
    monkeypatch.setattr(workspaces, 'approved_search_roots', lambda:[str(tmp_path)])
    return source


def test_document_evidence_and_source_change_invalidation(selected):
    document = docs.index_document(str(selected))
    response = docs.answer_with_sources('Warranty')
    assert response['sources'][0]['page'] == 1
    assert response['sources'][0]['content_hash'] == document['hash']
    assert 'not confirmed' in response['answer']
    selected.write_text('Completely changed source', encoding='utf-8')
    assert docs.search_documents('Warranty')['sources'] == []
    assert store.get('document', document['id'])['status'] == 'changed'


def test_task_requires_exact_evidence_and_revision_and_invalidates(selected):
    document = docs.index_document(str(selected))
    with pytest.raises(ValueError, match='quoted evidence'):
        docs.propose_task('Review', document['id'], 1, 'invented', '2026-12-01T09:00:00+05:30')
    task = docs.propose_task('Review', document['id'], 1, 'Review expiry 2026-12-01.', '2026-12-01T09:00:00+05:30')
    with pytest.raises(ValueError, match='changed'):
        docs.confirm_task(task['id'], 100)
    assert docs.confirm_task(task['id'], task['revision'])['status'] == 'confirmed'
    selected.unlink()
    assert docs.list_tasks()[0]['status'] == 'source_invalid'


def test_permission_revocation_filters_prior_index(selected, monkeypatch):
    docs.index_document(str(selected))
    monkeypatch.setattr('tools.documents.approved_search_roots', lambda:[])
    assert not docs.search_documents('receipt')['sources']


def test_reimport_invalidates_confirmed_deadline_from_previous_version(selected):
    document = docs.index_document(str(selected))
    task = docs.propose_task('Review', document['id'], 1, 'Review expiry 2026-12-01.', '2026-12-01T09:00:00+05:30')
    docs.confirm_task(task['id'], task['revision'])
    selected.write_text('Review expiry 2027-01-01.', encoding='utf-8')
    current = docs.index_document(str(selected))
    assert current['hash'] != document['hash']
    assert docs.list_tasks()[0]['status'] == 'source_invalid'


def test_failed_reimport_rolls_back_record_chunks_and_tasks(selected, monkeypatch):
    document = docs.index_document(str(selected))
    original = selected.read_text(encoding='utf-8')
    selected.write_text('New source version', encoding='utf-8')
    def fail(*args):
        raise RuntimeError('simulated write failure')
    monkeypatch.setattr(docs, '_invalidate_tasks', fail)
    with pytest.raises(RuntimeError, match='simulated'):
        docs.index_document(str(selected))
    assert store.get('document', document['id'])['hash'] == document['hash']
    selected.write_text(original, encoding='utf-8')
    assert 'receipt' in docs.search_documents('receipt')['sources'][0]['text']


def test_due_reminder_read_does_not_silently_acknowledge(selected):
    from routers.local_architecture import due_tasks
    document = docs.index_document(str(selected))
    task = docs.propose_task('Review', document['id'], 1, 'Payment on 2026-11-04.', '2020-01-01T09:00:00+05:30', 'inferred')
    confirmed = docs.confirm_task(task['id'], task['revision'])
    assert due_tasks()['tasks'][0]['id'] == task['id']
    assert due_tasks()['tasks'][0]['id'] == task['id']
    docs.acknowledge_task(task['id'], confirmed['revision'])
    assert due_tasks()['tasks'] == []
    assert store.get('document_task', task['id'])['status'] == 'confirmed'


def test_audit_does_not_copy_source_or_message_payload():
    from core import db
    db.init_db()
    db.log_audit('prepare_message_draft', {'recipient':'private@example.com','body':'Private sample text'},
                 'HIGH','allowed','Private sample text')
    with db.get_conn() as conn:
        row = conn.execute('SELECT args_json,result_summary FROM audit_log').fetchone()
    assert 'private@example.com' not in str(row)
    assert 'Private sample text' not in str(row)
    assert 'sha256' in row[0]


def test_periodic_workspace_capture_requires_opt_in_and_preserves_selection(selected):
    from core import workspace_scheduler as scheduler
    saved = workspaces.capture_workspace('Labelled demo', [{'kind':'file','target':str(selected)}], 'Fictional progress')
    policy = scheduler.configure(saved['id'],saved['revision'],False,5)
    with pytest.raises(ValueError, match='disabled'):
        scheduler.refresh_selected(policy)
    assert len(workspaces.find_workspace()) == 1
    policy = scheduler.configure(saved['id'],saved['revision'],True,5)
    snapshot = scheduler.refresh_selected(policy)
    assert snapshot['parent_workspace_id'] == saved['id']
    assert snapshot['context_note'] == 'Fictional progress'
    assert snapshot['items'][0]['target'] == str(selected.resolve())
    selected.unlink()
    with pytest.raises(FileNotFoundError):
        scheduler.refresh_selected(policy)
    assert len(workspaces.find_workspace()) == 2


def test_file_metadata_scan_continues_large_folder_and_filters_deleted_files(selected, monkeypatch):
    from core import file_index
    monkeypatch.setattr(file_index,'approved_search_roots',lambda:[str(selected.parent)])
    for number in range(2010):
        (selected.parent/f'item-{number}.txt').touch()
    result = file_index.index_files(str(selected.parent),10)
    assert result['status'] == 'partial'
    for _ in range(10):
        result = file_index.index_files(str(selected.parent),10)
        if result['status'] == 'complete':
            break
    assert result['status'] == 'complete'
    assert file_index.search_index('item-2009')['matches']
    (selected.parent/'item-2009.txt').unlink()
    assert not file_index.search_index('item-2009')['matches']


def test_conflicting_sources_remain_distinct(selected):
    first = docs.index_document(str(selected))
    other = selected.with_name('conflicting.txt')
    other.write_text('Warranty expiry 2027-12-01. Separate unsigned claim.', encoding='utf-8')
    second = docs.index_document(str(other))
    sources = docs.search_documents('Warranty expiry')['sources']
    assert {s['document_id'] for s in sources} == {first['id'],second['id']}


def test_workspace_revision_and_missing_item(selected):
    saved = workspaces.capture_workspace('Demo GCP', [{'kind':'file','target':str(selected)}], 'Demo only')
    with pytest.raises(ValueError, match='changed'):
        workspaces.restore_workspace(saved['id'], 9)
    selected.unlink()
    assert workspaces.preview_restore(saved['id'])['items'][0]['status'] == 'waiting_for_file'


@pytest.mark.parametrize('url', ['javascript:alert(1)','file:///C:/Windows/test.exe','https://user:pass@example.com'])
def test_workspace_rejects_unsafe_pages(url):
    with pytest.raises(ValueError):
        workspaces.capture_workspace('Unsafe', [{'kind':'tab','target':url}])


def test_workspace_executable_not_a_document(selected):
    program = selected.with_suffix('.exe'); program.write_bytes(b'not executable test data')
    with pytest.raises(ValueError):
        workspaces.capture_workspace('Unsafe', [{'kind':'file','target':str(program)}])


def test_restore_uses_review_and_exact_revision(selected):
    load_all_tools()
    saved = workspaces.capture_workspace('Demo', [{'kind':'file','target':str(selected)}])
    with pytest.raises(ToolNeedsConfirmation) as pending:
        dispatch('restore_workspace', {'workspace_id':saved['id'],'revision':saved['revision']})
    store.put('workspace', saved, saved['id'], saved['revision'])
    with pytest.raises(ValueError, match='changed'):
        execute_confirmed(pending.value.confirmation_id)


@pytest.mark.parametrize('available,cpu,expected', [(1,10,'low available'),(90,95,'CPU utilization'),(90,10,'No sustained')])
def test_diagnostics_separates_observation_and_hypothesis(available,cpu,expected):
    samples = [{'memory':{'available':available,'total':100},'cpu_per_core':[cpu,cpu]}]*30
    result = diagnostics.findings(samples)[0]
    assert expected in result['finding']
    assert result['evidence'] and result['hypothesis']


def test_diagnostics_distinguishes_commit_pressure_from_available_ram():
    sample={'memory':{'available':50,'total':100},'cpu_per_core':[10,10],
            'native_counters':{'values':{'committed_bytes':95,'commit_limit_bytes':100}}}
    findings=diagnostics.findings([sample]*30)
    assert any('committed-memory' in f['finding'] for f in findings)
    assert not any('low available' in f['finding'] for f in findings)


def test_diagnostics_does_not_promote_one_disk_spike_to_sustained_pressure():
    calm={'memory':{'available':50,'total':100},'cpu_per_core':[10],
          'native_counters':{'values':{'disk_active_percent':2}}}
    spike={**calm,'native_counters':{'values':{'disk_active_percent':100}}}
    assert not any('high disk activity' in f['finding'] for f in diagnostics.findings([calm]*29+[spike]))
    assert any('high disk activity' in f['finding'] for f in diagnostics.findings([spike]*30))


def test_named_workspace_restore_reviews_exact_revision_without_model(selected, monkeypatch):
    from routers import chat
    load_all_tools()
    snapshot=workspaces.capture_workspace('Suite delivery demo',[{'kind':'file','target':str(selected)}])
    monkeypatch.setattr(chat,'_call_model',lambda *a,**k:pytest.fail('Restore used a model'))
    response=asyncio.run(chat._perform(chat.ChatRequest(message='Restore workspace Suite delivery demo',session_id='test')))
    assert response.pending_confirmation
    from core import db
    row=db.get_pending_confirmation(response.pending_confirmation['id'])
    assert row['tool_name']=='restore_workspace'
    assert row['args']=={'workspace_id':snapshot['id'],'revision':snapshot['revision']}
    assert not store.records('restore')


def test_duplicate_workspace_names_require_exact_id(selected):
    first=workspaces.capture_workspace('Demo',[{'kind':'file','target':str(selected)}])
    second=workspaces.capture_workspace('Demo',[{'kind':'file','target':str(selected)}])
    with pytest.raises(ValueError,match='Choose an exact') as error:
        workspaces.resolve_workspace('Demo')
    assert first['id'] in str(error.value) and second['id'] in str(error.value)
    assert workspaces.resolve_workspace(second['id'])['workspace_id']==second['id']


def test_shared_gpu_wait_has_explanatory_service_response(monkeypatch):
    from routers import chat
    from core.resource_broker import GPUUnavailable
    from contextlib import contextmanager
    @contextmanager
    def occupied():
        raise GPUUnavailable('Waiting for StoryLens GPU work. It retains first priority.')
        yield
    monkeypatch.setattr('core.resource_broker.gpu_slot',occupied)
    with pytest.raises(chat.HTTPException) as error:
        asyncio.run(chat._call_model(None,[]))
    assert error.value.status_code==503
    assert 'Waiting for StoryLens' in error.value.detail


def test_restart_marks_unknown_and_invalidates_approvals():
    store.put('draft', {'status':'APPROVED','approval':{'consumed':False}}, 'draft1')
    store.put('draft', {'status':'SENDING','approval':{'consumed':True}}, 'draft2')
    store.recover()
    assert store.get('draft','draft1')['status']=='READY_FOR_REVIEW'
    assert store.get('draft','draft2')['status']=='UNCERTAIN'
    assert 'approval' not in store.get('draft','draft1')


def test_browser_unknown_is_not_requeued():
    from core.browser_bridge import exchange
    client='12345678-1234-1234-1234-123456789012'
    record=store.put('browser_command', {'client_id':client,'state':'pending','expires_at':time.time()+10})
    body={'client_id':client,'browser':'chrome','profile':'test'}
    assert len(exchange(body)['commands'])==1
    assert exchange(body)['commands']==[]
    assert store.get('browser_command',record['id'])['state']=='claimed'


def test_global_stop_revokes_unconsumed_review_cards(selected):
    from core.tool_registry import ConfirmationExpiredOrResolved
    load_all_tools()
    saved = workspaces.capture_workspace('Demo', [{'kind':'file','target':str(selected)}])
    with pytest.raises(ToolNeedsConfirmation) as pending:
        dispatch('restore_workspace', {'workspace_id':saved['id'],'revision':saved['revision']})
    assert tasks.cancel_all()['revoked_confirmations'] == 1
    with pytest.raises(ConfirmationExpiredOrResolved):
        execute_confirmed(pending.value.confirmation_id)


def test_secret_vault_stores_only_dpapi_ciphertext():
    from core import secret_store
    secret_store.save('test.fixture', 'fictional-local-secret-0042')
    assert secret_store.read('test.fixture') == 'fictional-local-secret-0042'
    assert 'fictional-local-secret-0042' not in secret_store._path().read_text()
    assert secret_store.names() == ['test.fixture']


def test_document_tools_cannot_import_cortana_private_runtime():
    from tools.files import within_approved_roots
    from core.config import ROOT_DIR
    assert not within_approved_roots(str(ROOT_DIR/'memory/private/secrets.dpapi.json'),[str(ROOT_DIR)])
    assert not within_approved_roots(str(ROOT_DIR/'logs/session.log'),[str(ROOT_DIR)])


def test_repeated_stop_holds_gpu_lease_until_bounded_inference_exits(monkeypatch):
    from contextlib import contextmanager
    from routers import chat
    events=[]
    @contextmanager
    def lease():
        events.append('held')
        try:
            yield
        finally:
            events.append('released')
    monkeypatch.setattr('core.resource_broker.gpu_slot',lease)
    async def scenario():
        started, finish = asyncio.Event(), asyncio.Event()
        async def inference(*args):
            started.set()
            await finish.wait()
            return {}
        monkeypatch.setattr(chat,'_call_ollama_with_slot',inference)
        task=asyncio.create_task(chat._call_ollama_raw(None,[]))
        await started.wait()
        task.cancel(); await asyncio.sleep(0)
        task.cancel(); await asyncio.sleep(0)
        assert events == ['held']
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events == ['held','released']
    asyncio.run(scenario())
