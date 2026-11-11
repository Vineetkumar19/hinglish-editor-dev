"""No real GPU, microphone or shared coordinator touched by these contracts."""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'agent'))
from core import model_profiles, resource_broker


@pytest.mark.parametrize('gpu_bytes,accepted', [(100,True),(60,False),(0,False)])
def test_reply_requires_full_gpu_residency(monkeypatch, gpu_bytes, accepted):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/api/ps':
            return httpx.Response(200,json={'models':[{'name':'fixture:9b','size':100,
                'size_vram':gpu_bytes,'context_length':4096}]})
        pytest.fail('Already resident model must not reload')
    monkeypatch.setattr('core.performance.record',lambda *a,**k:None)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await model_profiles.ensure_gpu_residency(client,'fixture:9b',{'num_ctx':4096},'30s')
    if accepted:
        assert asyncio.run(run())['size_vram'] == 100
    else:
        with pytest.raises(ValueError,match='not fully in VRAM'):
            asyncio.run(run())
    assert calls == ['/api/ps']


def test_cold_model_checks_placement_before_answer(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/api/chat':
            body=json.loads(request.content)
            assert body['messages'] == []
            assert body['options']['num_gpu'] == 33
            assert body['think'] is False
            return httpx.Response(200,json={})
        models = [] if len(calls)==1 else [{'name':'fixture:9b','size':100,'size_vram':100,'context_length':4096}]
        return httpx.Response(200,json={'models':models})
    monkeypatch.setattr('core.performance.record',lambda *a,**k:None)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await model_profiles.ensure_gpu_residency(client,'fixture:9b',{'num_ctx':4096,'num_gpu':33},'30s')
    asyncio.run(run())
    assert calls == ['/api/ps','/api/chat','/api/ps']


def test_stop_unloads_warm_weights_before_releasing_shared_slot(monkeypatch,tmp_path):
    events=[]
    monkeypatch.setattr('core.config.ROOT_DIR',tmp_path)
    monkeypatch.setattr(resource_broker,'_streams',[object()])
    monkeypatch.setattr(resource_broker,'_janitor',object())
    monkeypatch.setattr(resource_broker,'_warm_until',float('inf'))
    monkeypatch.setattr(resource_broker,'_unload_owned',lambda:events.append('unloaded'))
    monkeypatch.setattr(resource_broker,'_release_streams',lambda:events.append('released'))
    with resource_broker.gpu_slot():
        resource_broker.release_when_idle()
        assert events == []
    assert events == ['unloaded','released']


def test_priority_pause_prevents_new_gpu_work(monkeypatch,tmp_path):
    (tmp_path/'memory').mkdir()
    (tmp_path/'memory/pause_model_work').write_text('StoryLens priority')
    monkeypatch.setattr('core.config.ROOT_DIR',tmp_path)
    monkeypatch.setattr(resource_broker,'_streams',[])
    with pytest.raises(resource_broker.GPUUnavailable,match='StoryLens priority'):
        with resource_broker.gpu_slot():
            pytest.fail('Paused GPU work entered')
