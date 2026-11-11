"""Small integration boundary for the existing authenticated server POST handler.

Caller must perform its normal Host/origin/token checks before dispatch().
No workers are enabled here; Post only uses existing Publisher authorization.
"""
import threading

from hinglish_publish.prepare_post import PreparePost, buffer_status, candidates

_services = {}
_workflows = {}
_lock = threading.RLock()


def service(state, *, recover_delivery=True):
    with _lock:
        key = id(state)
        if key not in _services:
            _services[key] = PreparePost(state.publisher)
        engine = _services[key]
        if recover_delivery and not engine.delivery_running:
            if any(j.get('prepare_post_id') and j.get('authorized_at') and (j['status'] in ('ready', 'processing', 'scheduled')
                    or j['status'] == 'uploaded_private' and j.get('release_action') and j.get('release_authorized_at')) for j in state.publisher.store.list()):
                engine.start_delivery()
        return engine


def workflow_service(state, engine):
    with _lock:
        if id(state) not in _workflows:
            from hinglish_publish.prepare_post_workflow import Workflow
            _workflows[id(state)] = Workflow(state, engine)
        return _workflows[id(state)]


def dispatch(state, payload):
    engine = service(state, recover_delivery=payload.get('action') not in ('review-discovery','generate-weekly-seo','weekly-seo-list','weekly-seo-enable','weekly-seo-pause'))
    action, profile = payload.get('action', 'list'), payload.get('profile')
    if profile not in ('cricket', 'gaming'):
        raise ValueError('Choose Cricket or Gaming.')
    key = payload.get('id', '')
    if action == 'weekly-seo-list':
        from hinglish_publish.weekly_seo import Plans
        return {'plans':Plans(state.root).list(profile)}
    if action == 'weekly-seo-enable':
        from hinglish_publish.weekly_seo import Plans
        return Plans(state.root).enable(engine,profile,payload)
    if action == 'weekly-seo-pause':
        from hinglish_publish.weekly_seo import Plans
        return Plans(state.root).pause(key,profile,state.local_browser)
    if action == 'recover-schedule':
        from hinglish_publish.scheduling_recovery_agent import recover
        job = state.publisher.store.get(key)
        if job['profile'] != profile:
            raise ValueError('The saved schedule belongs to another profile.')
        recovered = recover(state.publisher, job)
        return {'recovered': recovered, 'job': key}
    if action == 'workflow-run':
        workflow = workflow_service(state, engine)
        value = workflow.get(key, profile) if key else workflow.create(payload)
        return workflow.start(value['id'], profile)
    if action == 'workflow-get':
        return workflow_service(state, engine).get(key, profile)
    if action == 'list':
        from .assistant_preferences import declarations
        from hinglish_publish.prepare_post_runtime import runtime_health
        from hinglish_publish.test_mode import enabled as repeat_uploads
        from hinglish_publish.weekly_seo import snapshot
        weekly_path=state.root/'cache/publisher/weekly-seo.sqlite3'
        return {'preparations': engine.list(profile), 'buffer': buffer_status(state.publisher.store.list(), profile),
                'weekly_seo_plans':snapshot(state.root,profile,state.local_browser) if weekly_path.is_file() else [],
                'discovery_supported':True,'weekly_seo_supported':True,
                'repeat_uploads_allowed': repeat_uploads(state.root, profile),
                'release_actions_supported': True,
                'simple_source_supported': True,
                'highlights_source_supported': True,
                'cancel_preparation_supported': True,
                'workflow_supported': True, 'workflows': workflow_service(state, engine).list(profile),
                'accounts': state.publisher.accounts(profile), 'declarations': declarations(state.root),
                'runtime': runtime_health(state.root),
                'visibility': state.publisher.settings(profile=profile).get('visibility', 'private'),
                'worker_enabled': engine.delivery_running or bool(state.publisher.thread and state.publisher.thread.is_alive())}
    if action == 'candidates':
        return candidates(payload.get('path', ''), payload.get('query', ''))
    if action == 'browse-video':
        from hinglish_publish.prepare_post_picker import browse
        path = payload.get('path') or state.publisher.settings(profile=profile).get('source_root') or str(state.root)
        return browse(path, payload.get('query', ''))
    if action in ('pick-video', 'pick-thumbnail'):
        from hinglish_publish.prepare_post_picker import native_pick
        initial = payload.get('path') or state.publisher.settings(profile=profile).get('source_root') or str(state.root)
        return {'path': native_pick(state.root, initial, kind='thumbnail' if action == 'pick-thumbnail' else 'video')}
    if action == 'publish-source':
        draft = engine.authorize_source(payload)
        key = draft['id']
        if draft['jobs_by_platform'].get('youtube'):
            return {'id': key, 'message': 'Using this video’s saved YouTube upload. No duplicate upload was created.'}
        action = 'start'
    if action == 'create':
        return engine.create(payload)
    if action == 'get':
        return engine.get(key, profile)
    if action == 'stop':
        return engine.cancel(key, profile)
    if action == 'cancel':
        return engine.cancel(key, profile, immediate=True)
    if action == 'edit':
        return engine.edit(key, profile, payload.get('platform'), payload.get('index'), payload.get('metadata', {}))
    if action == 'edit-thumbnail':
        return engine.edit_thumbnail(key, profile, payload.get('path', ''))
    if action in ('review-discovery','generate-weekly-seo'):
        if action == 'generate-weekly-seo':
            from hinglish_publish.weekly_seo_plan import schema
            schema(payload.get('weeks'))
        def review(progress=print):
            with state.work_lock:
                return engine.review_discovery(key, profile, payload.get('index', 1),
                    payload.get('live_research', True), progress,
                    weeks=payload.get('weeks') if action=='generate-weekly-seo' else None)
        with _lock:
            pending = getattr(engine, '_discovery_pending', set())
            if key in pending:
                return {'id':key,'message':'This preparation already has a queued SEO review.'}
            pending.add(key);engine._discovery_pending = pending
            def run_review(progress=print):
                try:
                    return review(progress)
                finally:
                    with _lock:pending.discard(key)
            try:
                task = state.publisher.task(run_review)
            except Exception:
                pending.discard(key)
                raise
        return {'id':key,'task':task,'message':'SEO review queued. Prepared media and publishing text are kept.'}
    if action == 'post':
        if payload.get('authorize') is not True:
            raise ValueError('Review the saved copy and press this platform’s Post button.')
        return engine.post(key, profile, payload.get('platform'), {k: payload[k] for k in ('made_for_kids', 'synthetic_media') if k in payload}, payload.get('release_action'))
    if action == 'start':
        draft = engine.get(key, profile)
        # Publisher.task serializes this publisher's preparations and exposes
        # stop/recovery diagnostics; work_lock serializes local requests and
        # each native stage worker owns the shared cross-process GPU lock.
        def work(progress=print):
            # Native stage workers own the cross-process GPU slot. Holding it
            # here would deadlock their GPU-only Ollama guard after ASR.
            with state.work_lock:
                return engine.run(key, profile, progress)
        with _lock:
            running = getattr(engine, '_submitted', set())
            if key in running:
                return {'id': key, 'message': 'Already queued or preparing.'}
            engine.resume(key, profile)
            running.add(key)
            engine._submitted = running
            def run(progress=print):
                try:
                    return work(progress)
                except Exception as error:
                    from .user_messages import failure
                    with engine.lock:
                        saved = engine.get(key, profile)
                        issue = failure(error, feature='Preparation queue')
                        saved['errors']['queue'] = issue
                        saved.update(status='failed', message=issue['error'])
                        engine._save(saved)
                    raise
                finally:
                    with _lock:
                        running.discard(key)
            task = state.publisher.task(run)
        return {'id': key, 'task': task, 'message': 'Queued for local preparation.', 'status': draft['status']}
    raise ValueError('Choose a supported preparation action.')
