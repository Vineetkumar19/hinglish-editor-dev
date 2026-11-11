"""Persistent chat sessions that dispatch the existing editor jobs, sequentially."""
import copy
import json
import re
import threading
import time
import uuid
from pathlib import Path

from .assistant_plan import TOOLS, job_payload, plan

ACTIVE = {'planning', 'running', 'transcribing'}
MEDIA = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.mts', '.m2ts', '.webm'}
ATTACHMENTS = MEDIA | {'.txt', '.xml', '.png', '.jpg', '.jpeg', '.webp', '.wav', '.m4a', '.ogg'}
from .assistant_creative_tools import AUDIO as CREATIVE_AUDIO
ATTACHMENTS |= CREATIVE_AUDIO


class Assistant:
    def __init__(self, state):
        self.state, self.root = state, state.root
        self.folder = self.root / 'cache' / 'assistant'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.sessions = {}
        from .conversation_memory import ConversationMemory
        self.memory=ConversationMemory(self.root)

    def _save(self, session):
        target = self.folder / (session['id'] + '.json')
        partial = target.with_name(target.stem+'.'+uuid.uuid4().hex+'.partial')
        try:
            partial.write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding='utf-8')
            # Windows readers/virus scanners can briefly deny replacement of
            # an open JSON file. A transient sharing lock must not kill a
            # scheduling worker while Chrome is completing its submission.
            for attempt in range(8):
                try:
                    partial.replace(target)
                    break
                except PermissionError:
                    if attempt==7:raise
                    time.sleep(min(.025*2**attempt,.4))
        finally:
            try:partial.unlink(missing_ok=True)
            except OSError:pass

    def _get(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r'[a-f0-9]{16}', session_id):
            raise ValueError('This conversation is unavailable. Start a new chat.')
        if session_id not in self.sessions:
            p = self.folder / (session_id + '.json')
            if not p.is_file():
                raise ValueError('This conversation is unavailable. Start a new chat.')
            session = json.loads(p.read_text(encoding='utf-8'))
            if session['status'] in ACTIVE:
                session.update(status='interrupted', stage='The app restarted. Completed results are kept. Send a new request to continue.',
                               job_id=None)
                # This can be a history read from a second local app instance.
                # Recovery status is local to this reader: do not overwrite the
                # active owner's durable session merely by opening its history.
            self.sessions[session_id] = session
        return self.sessions[session_id]

    def create(self):
        session = {'id': uuid.uuid4().hex[:16], 'created': time.time(), 'status': 'idle',
                   'messages': [], 'attachments': [], 'last_paths': [], 'last_result': None,
                   'step_results': [], 'selected': None, 'job_id': None, 'stage': '',
                   'steps': [], 'step_index': 0, 'stop': False, 'pending': None, 'brain': ''}
        with self.lock:
            self.sessions[session['id']] = session
            self._save(session)
        return copy.deepcopy(session)

    def snapshot(self, session_id):
        with self.lock:
            session = copy.deepcopy(self._get(session_id))
        if session.get('job_id'):
            try:
                session['job'] = self.state.snapshot(session['job_id'])
            except KeyError:
                pass
        if session.get('publishing_review'):
            from .assistant_upload_recovery import present
            session['publishing_review']=present(self,session)
            legacy_stage='Instagram slots queued locally; waiting for their release times.'
            if legacy_stage in session.get('stage',''):
                from .assistant_publish import instagram_waiting_message
                session['stage']=session['stage'].replace(legacy_stage,instagram_waiting_message(session['publishing_review']))
            from .pipeline_ledger import outcome
            session['workflow_status']=outcome(session['publishing_review'],session.get('pipeline_audit'))
            from .assistant_request_status import review_is_current
            session['workflow_status']['current_request']=review_is_current(session,session['publishing_review'])
            if not session['workflow_status']['current_request']:
                session['previous_workflow_status']=session['workflow_status']
                session['workflow_status']={'current_request':False,'complete':False,'delivery_count':0,
                    'summary':'Preparing this request','state':'preparing'}
        browser=getattr(self.state,'local_browser',None)
        if browser is not None:
            from .assistant_request_status import background_instagram
            with browser.lock:session['background_instagram']=background_instagram(session,browser.data['jobs'])
        # Old chat cards must display their matching durable result, not the
        # draft copy embedded before an automatic upload was queued.
        from .assistant_upload_recovery import present
        for message in session.get('messages',[]):
            if message.get('publishing_review'):
                message['publishing_review']=present(self,{**session,'publishing_review':message['publishing_review']})
        session['publishing_review_history']=[present(self,{**session,'publishing_review':r})
            for r in session.get('publishing_review_history',[])]
        from .assistant_progress import present as progress_view
        try:session['task_progress']=progress_view(self,session)
        except (OSError,ValueError,KeyError):session['task_progress']=None
        return session

    def _update(self, session_id, **values):
        with self.lock:
            session = self._get(session_id)
            session.update(values)
            if 'status' in values:session['status_updated_at']=time.time()
            self._save(session)
            from .progress_events import record
            record(self.root,'assistant',session_id,**{k:values[k] for k in ('status','stage','progress') if k in values})

    def _message(self, session_id, role, text, **values):
        if role=='assistant' and values.get('error'):
            from .user_messages import problem,diagnostics
            if not values.get('error_code'):
                issue=problem(text)
                values.setdefault('error_details',issue['details'])
                values.setdefault('error_code',issue['code'])
                text=issue['message']
            text=diagnostics(text)
            if values.get('error_details'):values['error_details']=diagnostics(values['error_details'])
        with self.lock:
            s = self._get(session_id)
            s['messages'].append({'id': uuid.uuid4().hex[:12], 'role': role, 'text': text,
                                  'created': time.time(), 'profile': s.get('profile', 'general'), **values})
            message=s['messages'][-1]
            if role=='user' and not s.get('title'):s['title']=text.replace('\n',' ')[:90]
            s['messages'] = s['messages'][-80:]
            self._save(s)
            self.memory.remember(s,message)
            return message['id']

    def _update_user_message(self,session_id,message_id,**values):
        with self.lock:
            session=self._get(session_id)
            message=next(m for m in session['messages'] if m['id']==message_id and m['role']=='user')
            message.update(values)
            if session.get('title')=='Voice message (transcribing…)':session['title']=message['text'].replace('\n',' ')[:90]
            self._save(session)
            self.memory.remember(session,message)

    def _progress(self, session_id, text):
        self._update(session_id, stage=str(text)[:250])

    def context_memory(self,text,session_id):
        """Compile verified software/media state, separately from old chat claims."""
        from .assistant_artifacts import catalog,evidence
        snapshot=self.snapshot(session_id)
        from .chat_context import memory as chat_memory
        memory=chat_memory(snapshot)
        from .workflow_memory import digest
        knowledge=snapshot.get('workflow_retrieval') or {}
        if knowledge.get('query_hash')==digest(text) and knowledge.get('chunks'):
            memory['workflow_knowledge']=knowledge
        from .assistant_publishing_context import active_context
        memory['active_task']=active_context(snapshot)
        memory['active_task'].pop('conversation',None)
        memory['saved_media']=evidence(catalog(self,snapshot))[:8]
        for turn in memory.get('messages',[]):turn['text']=turn['text'][:650]
        browser=self.state.local_browser.snapshot()
        from hinglish_cut.model_preferences import preferences
        prefs=preferences(self.root)
        memory['runtime_facts']={'tools':TOOLS,'planning_model':prefs.get('planning_model','installed local model'),
            'instagram':browser.get('readiness',{'connected':browser['connected']}),
            'knowledge_limits':'The local model has pretrained knowledge, not all Internet knowledge. '
                'Current online facts require a research tool and sources. General arbitrary browser/PC control is not implemented. '
                'Do not claim internet access or a tool capability merely because the user asks for it.',
            'execution_rules':'A saved local export is not an uploaded post. A queued post is not published. '
                'Use actual media IDs and receipts. Retry only supported recoverable steps; do not ask the user '
                'to rename an available file or repeat a resolved instruction. Never claim an execution succeeded before its result.'}
        from .assistant_distribution import context as workflow_context
        memory['runtime_facts']['assistant_execution']=workflow_context(self.root).get('assistant_execution',{})
        memory['runtime_facts']['pipeline_verification']={
            'command':'Check my whole pipeline',
            'behavior':'Read exact current YouTube results, validate saved video checksums and sampled decoding, inspect each Instagram queue receipt. No uploads or schedules are sent.',
            'plan_protection':'Check and protect my whole pipeline freezes file, account, metadata and release choices for safe continuation.',
            'completion':'A scheduled or locally queued future delivery keeps the workflow open until publication is verified.'}
        memory['runtime_facts']['caption_review']={
            'method':'The local model selects grounded spelling/name corrections; original word timings are preserved.',
            'numbers':'Cardinal and ordinal formatting uses digits. Malformed scores require independent local speech evidence; never guess from cricket records.',
            'heading_max_words':7,
            'repair_command':'Repair captions and headings of the saved Shorts uses their editable project, not another overlay or a new extraction.',
            'publication':'A caption repair produces revised local files. It does not change videos already uploaded to YouTube.'}
        return memory

    def save_upload(self, session_id, name, stream, length, kind='file'):
        with self.lock:
            self._get(session_id)
        name = Path(str(name).replace('\\', '/')).name
        extension = Path(name).suffix.lower()
        if not name or extension not in ATTACHMENTS:
            raise ValueError('Attach a video, .txt script, timeline XML or thumbnail picture.')
        if kind not in ('file', 'voice'):
            raise ValueError('Unknown attachment type')
        limit = 25 * 1024 ** 2 if kind == 'voice' else (100 * 1024 ** 3 if extension in MEDIA else 10 * 1024 ** 2)
        if not 0 < length <= limit:
            raise ValueError('This attachment is empty or too large.')
        if kind == 'voice' and extension not in {'.webm', '.wav', '.m4a', '.ogg'}:
            raise ValueError('Use a supported microphone recording.')
        folder = self.folder / 'uploads' / session_id
        folder.mkdir(parents=True, exist_ok=True)
        record_id = uuid.uuid4().hex[:12]
        target = folder / f'{record_id}-{name}'
        partial = target.with_suffix(target.suffix + '.partial')
        try:
            with partial.open('wb') as f:
                remaining = length
                while remaining:
                    chunk = stream.read(min(4 * 1024 ** 2, remaining))
                    if not chunk:
                        raise ValueError('Attachment transfer was interrupted. Add it again.')
                    f.write(chunk)
                    remaining -= len(chunk)
            partial.replace(target)
            return self.attach(session_id, target, name, record_id, kind)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    def attach(self, session_id, path, name=None, record_id=None, kind='file'):
        """Explicit local path selection is allowed; LLM plans cannot introduce paths."""
        path = Path(path).resolve()
        if not path.is_file() or path.suffix.lower() not in ATTACHMENTS:
            raise ValueError('This attachment is unavailable or unsupported.')
        item = {'id': record_id or uuid.uuid4().hex[:12], 'path': str(path), 'name': name or path.name,
                'kind': kind, 'size': path.stat().st_size}
        with self.lock:
            session = self._get(session_id)
            if len(session['attachments']) >= 100:
                raise ValueError('Start another chat after 100 attachments.')
            session['attachments'].append(item)
            self._save(session)
        return item

    def send(self, session_id, text, attachment_ids=None, voice_id=None, profile=None, motion_engine=None):
        from hinglish_niche.profiles import Profiles, valid_profile
        profile = valid_profile(profile or 'general')
        if not isinstance(text, str) or len(text) > 24000 or (not text.strip() and not voice_id):
            raise ValueError('Tell me what you want to make or edit.')
        with self.lock:
            s = self._get(session_id)
            if s['status'] in ACTIVE:
                from .assistant_schedule_status import requested,report
                if not voice_id and not attachment_ids and requested(text,s):
                    self._message(session_id,'user',text)
                    report(self,session_id,keep_running=True)
                    return self.snapshot(session_id)
                raise ValueError('Your current request is running. Stop after the current step, or wait for the result.')
            if profile != s.get('profile', 'general'):
                s['pipeline'] = None
                s['pending'] = None
                s['publishing_review'] = None
                s['campaign_pending'] = None
                s['campaign_user_turns'] = []
                s['last_paths'] = []
                s['shorts_paths'] = []
                s['highlights_paths'] = []
                s['original_paths'] = []
            s['profile'] = profile
            if motion_engine is not None:
                from hinglish_motion.engines import selected_engine
                s['motion_engine'] = selected_engine(text, motion_engine)
            if attachment_ids is None:
                attachment_ids = []
            if not isinstance(attachment_ids, list) or len(attachment_ids) > 100:
                raise ValueError('Invalid attachments')
            items = {a['id']: a for a in s['attachments']}
            if any(i not in items for i in attachment_ids):
                raise ValueError('An attachment belongs to another conversation or is unavailable.')
            if voice_id and (voice_id not in items or items[voice_id]['kind'] != 'voice'):
                raise ValueError('This voice recording is unavailable.')
            prior_steps=s.get('steps') or []
            if prior_steps and prior_steps[-1]['tool']=='distribute' and s.get('shorts_paths') and not s.get('publishing_review'):
                s['edit_publish_checkpoint']={'steps':copy.deepcopy(prior_steps),'result':copy.deepcopy(s.get('last_result')),
                    'profile':profile}
            s.update(status='transcribing' if voice_id else 'planning', stage='Listening locally…' if voice_id else 'Understanding your request…',
                     stop=False, selected=None, job_id=None, step_results=[], steps=[], step_index=0)
            self._save(s)
            message_id=self._message(session_id,'user',text.strip() or 'Voice message (transcribing…)',
                attachments=[items[i] for i in attachment_ids],voice=bool(voice_id),profile=profile)
            s.update(active_request_message_id=message_id,active_request_created=s['messages'][-1]['created'])
            self._save(s)
        thread = threading.Thread(target=self._respond, args=(session_id, text.strip(), attachment_ids, voice_id,message_id), daemon=True)
        thread.start()
        return self.snapshot(session_id)

    def stop(self, session_id):
        with self.lock:
            session = self._get(session_id)
            if session['status'] in ACTIVE or (session.get('pipeline') or {}).get('phase') in ('waiting_retry','waiting_executor'):
                session['stop'] = True
                session['stage'] = 'Stopping after the current step. Completed results will be kept.'
                if session['status'] not in ACTIVE:
                    session['pipeline']['phase']='paused'
                    session['pipeline']['next_retry']=0
                    session.update(status='stopped',stage='Automatic recovery paused. Completed results are kept.')
                self._save(session)
        return self.snapshot(session_id)

    def _stopped(self, session_id):
        with self.lock:
            return self._get(session_id)['stop']

    def retry_browser(self, job_id):
        from .assistant_social import monitor
        original = self.state.local_browser.get(job_id)
        session_id = original.get('session')
        if session_id:
            with self.lock:
                if self._get(session_id)['status'] in ACTIVE:
                    raise ValueError('This chat is already working. Wait for it to finish.')
        job = self.state.local_browser.retry_before_share(job_id)
        if session_id:
            self._update(session_id, status='running', stop=False, browser_job_id=job_id, stage=job['message'])
            threading.Thread(target=monitor, args=(self, session_id, job,
                lambda message: self._update(session_id, stage=message)), daemon=True).start()
        return job

    def _preflight(self, steps):
        for step in steps:
            tool = step['tool']
            if tool=='aivideo' and step['options'].get('video_method')=='motion':continue
            if tool in ('aiimage', 'aivideo') or (tool == 'thumbnail' and step['options'].get('generate_background')):
                from hinglish_aigen.engine import doctor
                status = doctor(self.root)
                field = 'video_model' if tool == 'aivideo' else 'image_model'
                if not status.get('cuda') or not status.get(field) or (tool == 'aivideo' and not status.get('image_model')):
                    raise ValueError(status.get('problem') or f'{TOOLS[tool]} needs its RTX model setup before it can run.')
            if tool == 'eyecontact':
                status = self.state.eyecontact_status()
                if not status['ready']:
                    raise ValueError('Eye Contact needs a supported RTX GPU and NVIDIA setup. ' +
                                     '; '.join(c['text'] for c in status['checks'] if not c['ok']))

    def _respond(self, session_id, text, attachment_ids, voice_id,message_id):
        progress = lambda m: self._progress(session_id, m)
        from .assistant_stream import reply_callback
        progress.stream_text=reply_callback(self,session_id,message_id)
        try:
            snapshot = self.snapshot(session_id)
            # Persist the accepted message immediately, but plan against the
            # preceding turns as before (e.g. an outline replies to old takes).
            snapshot['messages']=[m for m in snapshot['messages'] if m['id']!=message_id]
            from hinglish_niche.profiles import Profiles, use
            profile = snapshot.get('profile', 'general')
            context = Profiles(self.root).context(profile)
            from .assistant_campaign import requested as campaign_requested
            attachments = {a['id']: a for a in snapshot['attachments']}
            if voice_id:
                from .assistant_media import transcribe_voice
                with self.state.work_lock:
                    text = transcribe_voice(self.root, attachments[voice_id]['path'],progress=progress)
                self._update_user_message(session_id,message_id,text=text)
                if self._stopped(session_id):
                    self._update(session_id, status='stopped', stage='Voice request stopped.')
                    return
            selected = [attachments[i] for i in attachment_ids]
            # Ask for missing publishing inputs before retrieval or the large
            # planner. A short folder/account reply retains this chat's request.
            # Store the actual owner wording, not the resolved routing suffix.
            self._update_user_message(session_id,message_id,text=text,attachments=selected,voice=bool(voice_id),profile=profile)
            from .assistant_upload_workflow import followup as upload_workflow
            if upload_workflow(self,session_id,text,selected,progress,message_id):return
            from .assistant_prepare_post import followup as prepare_post
            if prepare_post(self,session_id,text,snapshot,selected,progress,message_id):return
            from .assistant_publish_intent import preflight
            text=preflight(self,session_id,text,snapshot,selected)
            if text is None:return
            from .assistant_creative_tools import requested as creative_requested,followup as creative_followup
            if creative_followup(self,session_id,text,progress):return
            creative_pending=snapshot.get('creative_pending')
            creative_continuation=bool(creative_pending and selected and re.fullmatch(r'\s*(?:here|these|attached|done|go ahead|start|yes|ok)[.!\s]*',text,re.I))
            creative_intent=creative_requested(text) or creative_continuation
            creative_text=(creative_pending['request']+'\nUser follow-up: '+text) if creative_continuation else text
            # Reference and sound-pack paths have distinct roles. Resolve this
            # explicit workflow before ordinary source-video folder discovery.
            from .assistant_plan import is_help_request
            from .assistant_motion_compare import execute as motion_compare
            if not creative_intent and not is_help_request(text) and motion_compare(self,session_id,text,profile):return
            from .assistant_motion_reference import execute as motion_reference
            if not creative_intent and not is_help_request(text) and motion_reference(self,session_id,text,profile):return
            if not creative_intent and profile == 'cricket' and context.get('topic') and not (campaign_requested(text) or snapshot.get('campaign_pending')):
                from hinglish_niche.research import fetch
                progress('Refreshing cricket research for this request…')
                fetch(self.root, profile, progress)
                context = Profiles(self.root).context(profile)
            from .assistant_saved_reels import requested as saved_reels_requested
            from .assistant_artifacts import editing_requested, catalog as artifact_catalog, evidence as artifact_evidence, resolve as resolve_artifact
            from .assistant_distribution import followup as distribute,gaming_recipe_requested,gaming_highlights_requested
            new_recipe=gaming_recipe_requested(text) or gaming_highlights_requested(text)
            fresh_edit=editing_requested(text) and not saved_reels_requested(text)
            if fresh_edit:self._update(session_id,edit_publish_checkpoint=None,pipeline=None)
            source_choice=bool(campaign_requested(text) and re.search(r'\b(?:choose|select|pick)\b',text,re.I) and re.search(r'[A-Za-z]:[\\/]',text))
            if fresh_edit and not any(Path(a['path']).suffix.lower() in MEDIA for a in selected if a['kind']!='voice'):
                from .assistant_sources import named_sources
                selected += [self.attach(session_id,p) for p in named_sources(text,[a['path'] for a in snapshot['attachments'] if a['kind']!='voice'])]
                from .assistant_visuals_source import requested as choose_visuals_source, choose as select_visuals_source
                if not selected and choose_visuals_source(text):
                    from hinglish_cut.gpu_lock import gpu_lock
                    progress('Choosing one video from your supplied folder…')
                    with self.state.work_lock, gpu_lock(self.root), use(context):
                        chosen, receipt = select_visuals_source(self.root, text, progress, context)
                    selected.append(self.attach(session_id, chosen))
                    self._update(session_id, visuals_source_selection=receipt)
            artifact_cards=artifact_catalog(self,snapshot) if fresh_edit and not new_recipe and not source_choice else []
            # An edit of a completed video is not a request to reuse/publish an
            # old Shorts campaign. Give the editor the actual runner artifacts.
            contextual_edit=fresh_edit and bool(artifact_cards or selected)
            edit_route=new_recipe or (contextual_edit and not source_choice)
            supplied_video=any(Path(a['path']).suffix.lower() in MEDIA for a in selected if a['kind']!='voice')
            if new_recipe and not any(Path(a['path']).suffix.lower() in MEDIA for a in selected if a['kind']!='voice'):
                literal=re.findall(r'([A-Za-z]:[\\/][^\r\n"<>|]*?\.(?:mp4|mkv|mov|webm|mxf))(?=\s|$|[".,;])',text,re.I)
                paths=[Path(p).resolve() for p in literal if Path(p).is_file()]
                if not paths:
                    raw=self.state.publisher.settings(profile='gaming').get('source_root','')
                    named=raw and re.search(re.escape(raw)+r'(?=$|[\s".,;])',text,re.I)
                    if named and Path(raw).is_dir():
                        base=Path(raw).resolve()
                        paths=sorted(p.resolve() for p in base.iterdir() if p.is_file() and p.suffix.lower() in MEDIA and p.resolve().is_relative_to(base))
                        if len(paths)>1:raise ValueError('The gaming folder has multiple recordings. Name the one to edit, or attach it in this chat.')
                if len(paths)>1:raise ValueError('Choose one gaming recording for the highlights edit.')
                selected += [self.attach(session_id,p) for p in paths]
            from .chat_context import recent
            from hinglish_cut.feature_context import history_options
            history=recent([m for m in snapshot['messages'] if m.get('profile','general')==profile and m['id']!=message_id], **history_options(self.root))
            self._update_user_message(session_id,message_id,attachments=selected,voice=bool(voice_id),profile=profile)
            self._update(session_id, status='planning',workflow_retrieval=None)
            from .assistant_plan import is_help_request
            help_request=is_help_request(text)
            from .pipeline_audit import followup as audit_pipeline
            if audit_pipeline(self,session_id,text,snapshot):return
            from .assistant_instagram_verification import followup as verify_instagram
            if verify_instagram(self,session_id,text,snapshot):return
            from .assistant_schedule_status import followup as schedule_status
            if schedule_status(self,session_id,text,snapshot,selected):return
            from .assistant_metadata_repair import followup as repair_copy
            if repair_copy(self,session_id,text,snapshot,progress):return
            from .assistant_post_now import followup as post_saved_now
            if post_saved_now(self,session_id,text,snapshot):return
            from .assistant_pipeline import resume_saved
            if not selected and resume_saved(self,session_id,text,snapshot):return
            from .assistant_caption_repair import execute as repair_saved_captions
            if not selected and repair_saved_captions(self,session_id,text,snapshot,progress):return
            from .assistant_edit_workflow import resume as resume_edit_publish
            if resume_edit_publish(self,session_id,text,snapshot,progress):return
            from .assistant_publish import confirmation, start as publish_reviewed
            reply=confirmation(text,snapshot.get('publishing_review'),self.root)
            if reply:
                publish_reviewed(self,{'session':session_id,**reply},internal=True)
                return
            from .workflow_memory import WorkflowMemory,configuration as workflow_memory_config,relevant as workflow_memory_relevant
            if workflow_memory_config(self.root).get('enabled') and workflow_memory_relevant(text):
                # Retrieve before opening the planner, under the same work/GPU
                # locks as other local engines. Never evict an active media model.
                from hinglish_cut.gpu_lock import gpu_lock
                progress('Waiting for the shared local-model queue…')
                with self.state.work_lock,gpu_lock(self.root):
                    progress('Reading your saved workflow guidance…')
                    knowledge=WorkflowMemory(self.root).retrieve(text,progress)
                self._update(session_id,workflow_retrieval=knowledge,
                    stage='Using the saved workflow to answer your request' if knowledge.get('chunks') else 'Understanding your request')
            if edit_route:self._update(session_id,campaign_pending=None)
            from .assistant_saved_reels import followup as saved_reels
            if not help_request and not supplied_video and saved_reels(self,session_id,text,progress):return
            if not help_request and not edit_route and not supplied_video and distribute(self,session_id,text,progress):return
            from .assistant_campaign import followup
            if not help_request and not edit_route and not supplied_video and followup(self,session_id,text,progress):return
            from .assistant_campaign import requested as campaign_requested, execute as prepare_campaign
            if not help_request and not edit_route and (campaign_requested(text) or snapshot.get('campaign_pending')):
                prepare_campaign(self,session_id,text,progress)
                return
            if not help_request and not edit_route and snapshot.get('campaign') and re.search(r'\b(upload|post)\b',text,re.I) and re.search(r'\bprivate(?:ly)?\b',text,re.I) \
                    and not re.search(r'\b(how|do not|don.t|never)\b',text,re.I) and not snapshot.get('publishing_review'):
                from .assistant_campaign import stage_review
                stage_review(self,session_id)
                return
            from .assistant_publish import request as publishing_request, prepare as prepare_publication, confirmation, start as publish_reviewed
            reply = confirmation(text, snapshot.get('publishing_review'),self.root)
            if reply:
                publish_reviewed(self, {'session': session_id, **reply}, internal=True)
                return
            publication = None if edit_route or help_request else publishing_request(text, profile)
            if publication:
                if publication.get('question'):
                    self._message(session_id, 'assistant', publication['question'], question=True)
                    self._update(session_id, status='idle', stage='')
                    return
                self._update(session_id, brain='Saved YouTube workflow · local model writes metadata')
                prepare_publication(self, session_id, text, selected, publication, progress)
                return
            pending = snapshot.get('pending')
            # A reply to an attachment request reuses the plan without another expensive inference.
            if pending and attachment_ids and re.fullmatch(r'(here|these|attached|done|go ahead|start|yes|ok)[.! ]*', text.casefold()):
                parsed, brain = pending, 'Continued editor request'
            else:
                memory_context=self.context_memory(text,session_id)
                if artifact_cards and not any(Path(a['path']).suffix.lower() in MEDIA for a in selected if a['kind']!='voice'):
                    memory_context['editing_sources']=artifact_evidence(artifact_cards)
                with self.state.work_lock, use(context):
                    from .assistant_creative_tools import source_catalog
                    plan_attachments=(source_catalog(selected) if creative_intent else
                                      [{'name': a['name'], 'kind': Path(a['path']).suffix} for a in selected])
                    parsed, brain = plan(self.root, creative_text, history,
                                         plan_attachments,
                                         bool(snapshot['last_paths']), progress,
                                         memory_context=memory_context,
                                         browser_context={k:v for k,v in self.state.local_browser.snapshot().items() if k != 'jobs'})
            if self._stopped(session_id):
                self._update(session_id, status='stopped', stage='Stopped before starting any new editing step.')
                return
            self._update(session_id, brain=brain)
            knowledge=self.snapshot(session_id).get('workflow_retrieval') or {}
            if knowledge.get('chunks') and brain not in ('Direct editor command','Continued editor request'):
                self._update(session_id,workflow_retrieval={**knowledge,'planner':brain,
                    'planner_context_ids':[r['id'] for r in knowledge['chunks']]})
            if parsed['question'] or not parsed['steps']:
                self._message(session_id, 'assistant', parsed['question'] or parsed['reply'], question=bool(parsed['question']))
                self._update(session_id, status='idle', stage='', pending=None)
                if creative_intent and parsed['question']:
                    self._update(session_id,creative_pending={'request':creative_text})
                return
            steps = parsed['steps']
            if any(s['tool'] in ('beats','cinematic') for s in steps):
                from .assistant_creative_tools import execute as execute_creative
                execute_creative(self,session_id,parsed,selected,profile,progress)
                return
            if fresh_edit and edit_route:
                # The history retains old receipts. The active edit must not
                # inherit a review/campaign belonging to a different source.
                self._update(session_id,publishing_review=None,campaign=None,campaign_memory_ref=None)
            if steps[0]['tool'] == 'instagram':
                from .assistant_social import execute
                self._update(session_id, selected='instagram', steps=steps, pending=None)
                execute(self, session_id, text, selected, snapshot, steps[0]['options'], progress)
                return
            self._update(session_id, selected=steps[0]['tool'], payload=job_payload(steps[0], [], '', root=self.root))
            if steps[0]['tool'] == 'publish':
                opt = steps[0]['options']
                prepared_shorts = snapshot.get('shorts_paths', []) if profile == 'gaming' and opt.get('make_shorts') else []
                videos = [a['path'] for a in selected if a['kind'] != 'voice' and Path(a['path']).suffix.lower() in MEDIA]
                videos = videos or snapshot['last_paths']
                thumbnail = next((a['path'] for a in selected if Path(a['path']).suffix.lower() in {'.png', '.jpg', '.jpeg'}), '')
                progress('Preparing English publishing drafts…')
                self._update(session_id, status='running', steps=steps)
                with self.state.work_lock:
                    if videos:
                        ids = []
                        for video in videos:
                            if self._stopped(session_id): break
                            if Path(video).suffix.lower() != '.mp4':
                                raise ValueError('Publishing needs a finished MP4 export. Attach an MP4 or finish your edit first.')
                            result = self.state.publisher.prepare_file({'video': video, 'kind': opt.get('publish_kind', 'long'),
                                                                         'thumbnail': thumbnail},
                                                                        {'notes': text, 'make_shorts': opt.get('make_shorts', False) and not prepared_shorts, 'profile': profile,
                                                                         'shorts_source': video}, progress)
                            ids += result['job_ids']
                        for short in prepared_shorts:
                            if self._stopped(session_id): break
                            result = self.state.publisher.prepare_file({'video': short, 'kind': 'short', 'thumbnail': ''},
                                {'notes': text, 'profile': profile}, progress)
                            ids += result['job_ids']
                    else:
                        result = self.state.publisher.prepare({'name': text, 'notes': '', 'profile': profile,
                                                               'make_shorts': opt.get('make_shorts', False)}, progress)
                        ids = result['job_ids']
                self._message(session_id, 'assistant', f'{len(ids)} publishing posts prepared as editable drafts in English. Review the account, audience and schedule in Publishing Studio, then authorize publication.',
                              navigate='publisher', command=text, publish_ids=ids,publisher_profile=profile)
                self._update(session_id, status='complete', stage='Publishing drafts ready', pending=None, selected='publish')
                return
            files = [a['path'] for a in selected if a['kind'] != 'voice' and Path(a['path']).suffix.lower() in MEDIA]
            if not files and parsed.get('source_id'):
                files=resolve_artifact(artifact_cards,parsed['source_id'])
                self._update(session_id,edit_source={'id':parsed['source_id'],'paths':files})
            if new_recipe and not files:
                # Only a literal path in the user's new request can supply a new
                # source here; an LLM-generated path is never accepted.
                explicit=re.findall(r'([A-Za-z]:[\\/][^\r\n"<>|]*?\.(?:mp4|mkv|mov|webm|mxf))(?=\s|$|[".,;])',text,re.I)
                files=[str(Path(p).resolve()) for p in explicit if Path(p).is_file()]
                if len(files)>1:raise ValueError('Choose one livestream recording for this highlights workflow.')
            xml = next((a['path'] for a in selected if Path(a['path']).suffix.lower() == '.xml'), None)
            if xml:
                from .assistant_media import render_xml
                folder = self.root / 'output' / 'assistant' / ('source-' + uuid.uuid4().hex[:8])
                folder.mkdir(parents=True)
                with self.state.work_lock:
                    files = [render_xml(xml, folder / 'timeline-source.mp4', progress)]
            script_files = [a for a in selected if Path(a['path']).suffix.lower() == '.txt']
            script = '\n\n'.join(Path(a['path']).read_text(encoding='utf-8-sig') for a in script_files)
            if len(script) > 100000:
                raise ValueError('Please keep your attached script under 100,000 characters.')
            if not files and not new_recipe:
                files = snapshot['last_paths']
            if not files and not snapshot['last_paths'] and not new_recipe:
                # Reuse the attachments supplied with the previous request, e.g. clarification replies.
                for m in reversed(snapshot['messages']):
                    prior = m.get('attachments', []) if m.get('profile', 'general') == profile else []
                    if prior:
                        files = [a['path'] for a in prior if Path(a['path']).suffix.lower() in MEDIA and a['kind'] != 'voice']
                        if not script:
                            script = '\n\n'.join(Path(a['path']).read_text(encoding='utf-8-sig')
                                                for a in prior if Path(a['path']).suffix.lower() == '.txt')
                        break
            standalone = all(s['tool'] in ('aiimage', 'aivideo', 'motion', 'thumbnail') and (s['options'].get('script') or script) for s in steps)
            if not files and not standalone:
                self._message(session_id, 'assistant', 'Attach the video clips here, then send “Start.” I’ll keep these editing settings.', question=True)
                self._update(session_id, status='idle', pending=parsed, stage='Waiting for your videos')
                return
            if any(s['tool'] == 'script' and not (s['options'].get('script') or script) for s in steps):
                self._message(session_id, 'assistant', 'Attach your .txt script or paste the outline after “Script:”. I’ll use it to arrange these clips by meaning.', question=True)
                self._update(session_id, status='idle', pending=parsed, stage='Waiting for your script')
                return
            if any(not Path(p).is_file() for p in files):
                raise ValueError('A video has moved or is unavailable. Please attach it again.')
            from hinglish_publish.features import features
            if not features(self.root)['burn_in_captions']:
                if steps and steps[-1]['tool']=='distribute':steps=[step for step in steps if step['tool']!='captions']
                for step in steps:
                    if step['tool']=='shorts':step['options']['captions']=False
            self._preflight(steps)
            from .assistant_pipeline import begin
            begin(self,session_id,text,steps,files)
            self._message(session_id, 'assistant', parsed['reply'] or 'I’ll start your edit.',
                          plan=[TOOLS[s['tool']] for s in steps], combine=parsed['combine'])
            self._update(session_id, status='running', pending=None, steps=steps)
            run_folder = self.root / 'output' / 'assistant' / f'{session_id}-{uuid.uuid4().hex[:8]}'
            run_folder.mkdir(parents=True)
            original_files = list(files)
            if profile == 'gaming':
                attached_videos = [a['path'] for a in selected if a['kind'] != 'voice' and Path(a['path']).suffix.lower() in MEDIA]
                original_files = attached_videos or (list(files) if new_recipe else snapshot.get('original_paths') or list(files))
                self._update(session_id, original_paths=original_files)
            if profile!='gaming':self._update(session_id,original_paths=original_files)
            for index, step in enumerate(steps):
                if self._stopped(session_id):
                    break
                if step['tool']=='distribute':
                    from .assistant_pipeline import checkpoint
                    checkpoint(self,session_id)
                    from .assistant_distribution import from_outputs
                    from_outputs(self,session_id,step['options'],text,progress)
                    return
                if profile == 'gaming' and step['tool']=='gaming':
                    files = original_files
                payload = job_payload(step, files, script, root=self.root)
                if step['tool'] == 'motion':
                    from hinglish_motion.engines import selected_engine
                    payload['motion_engine'] = selected_engine(text, self._get(session_id).get('motion_engine') or payload.get('motion_engine') or 'remotion')
                if step['tool']=='shorts' and re.search(r'\b(?:new|fresh|different)\b.{0,40}\b(?:short|clip|moment)',text,re.I):
                    payload['shorts_fresh']=True
                payload['profile'] = profile
                if step['tool'] == 'motion' and profile == 'cricket' and 'motion_style' not in payload:
                    reference = context.get('documentary_reference', {})
                    if reference.get('motion_style'): payload['motion_style'] = reference['motion_style']
                if step['tool'] == 'thumbnail':
                    pictures = [a['path'] for a in selected if Path(a['path']).suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}]
                    if pictures: payload['reference' if step['options'].get('image_reference_role')=='style' else 'portrait'] = pictures[0]
                    if len(pictures) > 1: payload['background'] = pictures[1]
                # Chat attachments stay available for follow-ups; the ordinary uploader is disposable.
                self._update(session_id, selected=step['tool'], step_index=index, stage=f'Starting {TOOLS[step["tool"]]}')
                job = self.state.create_job(payload)
                self._update(session_id, job_id=job['id'], payload=payload)
                while True:
                    job = self.state.snapshot(job['id'])
                    if job['status'] in ('complete', 'failed'):
                        break
                    threading.Event().wait(.4)
                if job['status'] == 'failed':
                    if step['tool']=='visuals':
                        from .visual_clarification import pause as pause_visual_question
                        if pause_visual_question(self,session_id,job,text,payload):return
                    raise ValueError(f'{TOOLS[step["tool"]]} could not finish: {job["stage"]}')
                result = job['result']
                with self.lock:
                    s = self._get(session_id)
                    s['last_result'] = result
                    s['step_results'].append({'tool': step['tool'], 'result': result})
                    self._save(s)
                quality = result.get('quality_summary')
                if step['tool']=='sound' and result.get('sound_recommendations'):
                    self._message(session_id,'assistant',
                        'Sound suggestions are ready for review. In your editor’s Storylens panel, open Saved sound review. '
                        'Listen to the alternatives, then import only the original recordings you choose. '
                        'No full mix or automatic timeline placement was created.',result=result)
                    self._update(session_id,status='needs_review',stage='Review the sound alternatives',job_id=None)
                    return
                if step['tool']=='visuals' and result.get('visuals_summary',{}).get('review_options'):
                    summary=result['visuals_summary']
                    from .visual_review_text import message as visual_review_message
                    message=visual_review_message(summary,raw=payload.get('visuals_review_options') is True and payload.get('visuals_popups') is False)
                    self._message(session_id,'assistant',message,result=result)
                    self._update(session_id,status='needs_review',stage='Choose your visual references',job_id=None)
                    return
                if step['tool']=='broll' and result.get('broll_summary',{}).get('filled')==0:
                    message='No relevant video passed the B-roll context check. Your original source and audio are kept; the missing moments stay empty. Review the search results or try another footage source.'
                    self._message(session_id,'assistant',message,result=result)
                    self._update(session_id,status='needs_review',stage='No relevant B-roll found',job_id=None)
                    return
                if quality and not quality['passed']:
                    self._message(session_id, 'assistant', 'This step needs review: ' + '; '.join(quality['failed']) + '. I’ve kept the results and paused the remaining steps.', result=result)
                    self._update(session_id, status='needs_review', stage='Review the quality report', job_id=None)
                    return
                from .assistant_media import outputs, join_videos
                with self.state.work_lock:
                    files = outputs(self.root, step, result, run_folder, progress)
                    if parsed['combine'] and len(files) > 1 and step['tool'] != 'shorts':
                        from hinglish_cut.compute_policy import heavy_device
                        files = [join_videos(files, run_folder / 'joined', progress,device=heavy_device(self.root))]
                self._update(session_id, last_paths=files, job_id=None)
                if step['tool'] == 'shorts':
                    self._update(session_id, shorts_paths=files)
                    wanted = step['options'].get('count')
                    if str(wanted).isdigit() and len(files) < int(wanted):
                        message=(f'{len(files)} of {wanted} requested Shorts could be extracted from complete, unused moments. '
                                 'No uploads started. Try another source or request fewer clips.')
                        self._message(session_id, 'assistant', message, result=result, videos=files)
                        self._update(session_id, status='needs_review', stage=message, job_id=None)
                        return
                    if steps[-1]['tool']=='distribute':
                        from .assistant_pipeline import checkpoint
                        checkpoint(self,session_id)
                if step['tool'] == 'gaming':
                    self._update(session_id,highlights_paths=files)
                handoff=' Continuing with the requested upload.' if index+1<len(steps) and steps[index+1]['tool']=='distribute' else ''
                from .user_messages import extracted
                completed=extracted(len(files)) if step['tool']=='shorts' else f'{TOOLS[step["tool"]]} complete.'
                self._message(session_id, 'assistant', completed+handoff,
                              result=result, videos=files)
                if not files and index + 1 < len(steps):
                    raise ValueError('This step generated an asset library. Choose the assets in its review before continuing with a video edit.')
            stopped = self._stopped(session_id)
            self._update(session_id, status='stopped' if stopped else 'complete', job_id=None,
                         stage='Stopped. Completed results are kept.' if stopped else 'Your request is complete.')
            if stopped:
                self._message(session_id, 'assistant', 'Stopped after the current step. Your completed results are kept.')
        except Exception as error:
            with self.lock:
                from .user_messages import problem
                issue=problem(error)
                self._message(session_id, 'assistant', issue['message'], error=True,error_details=issue['details'],error_code=issue['code'],result=self.snapshot(session_id).get('last_result'))
                self._update(session_id, status='failed', stage=issue['message'],error_details=issue['details'],error_code=issue['code'],job_id=None)
                from .assistant_pipeline import failed
                failed(self,session_id,error)
