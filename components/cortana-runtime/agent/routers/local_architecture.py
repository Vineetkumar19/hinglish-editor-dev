"""Narrow authenticated UI surface. All mutations use the same tool policy."""
import asyncio
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from core import local_store as store, tasks
from core.tool_registry import dispatch, ToolNeedsConfirmation
from tools.documents import PathNotApproved

router = APIRouter(tags=['local-workflows'])
ALLOWED = {'index_document','search_documents','answer_with_sources','list_document_tasks',
    'build_document_embeddings','semantic_document_search','index_file_metadata','search_file_index',
    'inspect_local_data','export_local_data','prune_local_history',
    'inspect_process','unload_cortana_model',
    'propose_document_task','confirm_document_task','acknowledge_document_task','finish_document_task','forget_document','find_workspace','capture_workspace',
    'preview_restore','restore_workspace','configure_workspace_capture','capture_browser_workspace','list_browser_profiles',
    'find_browser_tab','focus_browser_tab','read_browser_tab','calendar_availability',
    'sample_system','compare_diagnostics','model_profiles','switch_model_profile'}


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: str
    arguments: dict = Field(default_factory=dict)
    request_id: str = Field(default_factory=lambda:uuid4().hex, pattern=r'^[a-zA-Z0-9_-]{8,80}$')


@router.post('/api/local/stop')
def stop():
    return tasks.cancel_all()


@router.get('/api/local/state')
def state():
    from core.personal_documents import list_tasks
    return {'documents':store.records('document'), 'workspaces':store.records('workspace'),
            'tasks':list_tasks(), 'diagnostics':[{k:v for k,v in r.items() if k not in {'samples'}} for r in store.records('diagnostic',20)],
            'browser_profiles':store.records('browser_profile'), 'workspace_schedules':store.records('workspace_schedule'), 'cloud_enabled':False}


@router.get('/api/local/tasks/due')
def due_tasks():
    from core.personal_documents import list_tasks
    # Reading must not silently mark a reminder delivered, including on wake.
    return {'tasks':[t for t in list_tasks() if t['overdue'] and not t['acknowledged']]}


@router.post('/api/local/action')
async def action(body: Action):
    if body.tool not in ALLOWED:
        raise HTTPException(403, 'This workflow action is unavailable.')
    token = tasks.begin(body.request_id)
    try:
        result = await run_in_threadpool(dispatch, body.tool, body.arguments)
        return {'result':result, 'request_id':body.request_id}
    except ToolNeedsConfirmation as exc:
        return {'pending_confirmation':{'id':exc.confirmation_id, 'tool_name':exc.tool_name, 'preview':exc.preview},
                'request_id':body.request_id}
    except asyncio.CancelledError:
        raise HTTPException(409, 'Task stopped; no further steps will start.')
    except (ValueError, OSError, RuntimeError, PathNotApproved) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        tasks.finish(body.request_id, token)


class CaptureBrowser(BaseModel):
    model_config = ConfigDict(extra='forbid')
    browser: str = Field(pattern=r'^(chrome|brave)$')
    profile: str = Field(min_length=1,max_length=100)
    name: str = Field(min_length=1,max_length=120)
    items: list[dict] = Field(default_factory=list,max_length=49)
    context_note: str = Field(default='',max_length=4000)
    request_id: str = Field(default_factory=lambda:uuid4().hex, pattern=r'^[a-zA-Z0-9_-]{8,80}$')


@router.post('/api/local/capture-browser')
async def capture_browser(body: CaptureBrowser):
    token = tasks.begin(body.request_id)
    try:
        return {'result':await run_in_threadpool(dispatch, 'capture_browser_workspace',
            body.model_dump(exclude={'request_id'}))}
    except asyncio.CancelledError:
        raise HTTPException(409, 'Capture stopped; no workspace was saved.')
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        tasks.finish(body.request_id, token)
