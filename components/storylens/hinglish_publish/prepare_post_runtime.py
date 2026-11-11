"""Production local tools for Prepare/Post. Invoked only inside the shared GPU lock.

No cloud writer, placeholder metadata, thumbnail generation, or upload transport.
"""
import json
import hashlib
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from hinglish_app.durable_json import write
from .prepare_post import file_identity, verify_identity, text_chunks


def inference_device(root):
    from hinglish_cut.model_preferences import preferences
    config = preferences(root)
    device = config.get('device', 'cuda' if config.get('require_cuda_inference') else 'cpu')
    if device not in ('cpu', 'cuda'):
        raise ValueError('Choose CPU or CUDA in the local model settings before preparation.')
    if config.get('require_cuda_inference') and device != 'cuda':
        raise ValueError('Local model settings require CUDA. Select CUDA before preparing; CPU fallback was not used.')
    return device


def runtime_connection(root):
    from hinglish_cut.model_preferences import preferences
    config = preferences(root)
    python = Path(config.get('cuda_runtime_python') or sys.executable)
    return {'provider': 'ollama', 'planning_model': config.get('planning_model', 'qwen3:8b'),
            'runtime_python': str(python), 'runtime_available': python.is_file(),
            'stages': ['speech', 'selection', 'render', 'youtube_copy', 'instagram_copy'],
            'inference_verified': False}


def runtime_health(root):
    """Passive local inventory only; never starts a server, loads a model or pulls."""
    import urllib.request
    result = runtime_connection(root)
    result.update(service_online=False, planning_model_installed=False)
    try:
        # This endpoint is loopback-only, like OllamaBrain's trust_env=False
        # session. A system web proxy must not turn local readiness into an
        # external request or falsely report an installed model as offline.
        local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with local.open('http://127.0.0.1:11434/api/tags', timeout=1) as response:
            models = [item['name'] for item in json.load(response).get('models', [])]
        selected = result['planning_model']
        result.update(service_online=True, planning_model_installed=selected in models or selected + ':latest' in models)
    except (OSError, ValueError, KeyError):
        pass
    return result


class StageWorkerError(ValueError):
    def __init__(self, details):
        super().__init__('The local preparation worker stopped. Resume the unfinished stage; completed work is saved.')
        self.stderr = details


class IsolatedRuntime:
    """Keep native ASR/render imports out of the long-lived HTTP service."""
    def __init__(self, root):
        self.root = Path(root).resolve()

    def command(self, request):
        python = Path(runtime_connection(self.root)['runtime_python'])
        if not python.is_file():
            raise ValueError('The configured local runtime is unavailable. Check model settings before preparing this source.')
        return [str(python), '-E', '-X', 'utf8', '-m', 'hinglish_publish.prepare_post_worker', '--request', str(request)]

    def stage(self, stage, draft, progress):
        folder = self.root / 'output/publisher-prepare-post/preparations' / draft['id'] / 'workers' / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        request = folder / 'request.json'
        write(request, {'root': str(self.root), 'stage': stage, 'draft': draft})
        command = self.command(request)
        started = time.time()
        # Parent dispatch owns only the application work lock. This native child
        # owns the shared GPU slot, including reentrant Ollama residency checks.
        # No diagnostic timeout stops a healthy stage.
        with (folder / 'worker.log').open('wb') as log:
            process = subprocess.Popen(command, cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            last = ''
            try:
                while process.poll() is None:
                    check_cancel = getattr(progress, 'check_cancel', None)
                    if check_cancel:check_cancel()
                    try:
                        message = json.loads((folder / 'progress.json').read_text('utf-8'))['message']
                    except (OSError, ValueError, KeyError):
                        message = ''
                    if message and message != last:
                        progress(message)
                        last = message
                    time.sleep(.25)
            except BaseException:
                # A failed owner callback must not release the shared GPU lock
                # while leaving its native child running unowned.
                from hinglish_app.publishing_speech import stop_owned
                stop_owned(process)
                raise
        write(folder / 'exit.json', {'exit_code': process.returncode, 'elapsed_seconds': round(time.time() - started, 2)})
        result = folder / 'result.json'
        if process.returncode or not result.is_file():
            raise StageWorkerError('Stage: ' + stage + '\nExit: ' + str(process.returncode) + '\n' + (folder / 'worker.log').read_text('utf-8', errors='replace')[-14000:])
        return json.loads(result.read_text('utf-8'))


class RecordedBrain:
    def __init__(self, brain, folder, context):
        self.brain, self.folder, self.context = brain, folder, context
        self.name = brain.name
        self._receipt_paths = {}
        self._provider_cache_paths = {}

    def reject_result(self, result, error):
        """Retain the rejected receipt, but never reuse it as a successful answer."""
        targets=self._receipt_paths.get(id(result))
        if not targets:return
        from hinglish_app.user_messages import diagnostics
        for target in targets:
            saved=json.loads(target.read_text('utf-8'))
            saved.update(status='rejected',validation_error=diagnostics(error))
            archive=target.with_name(target.stem+'-rejected-'+str(time.time_ns())+'.json')
            write(archive,saved);write(target,saved)
        provider=self._provider_cache_paths.get(id(result))
        cache=getattr(self.brain,'cache',None)
        if isinstance(provider,Path) and isinstance(cache,Path) and provider.parent.resolve()==cache.resolve() and provider.is_file():
            # Preserve the old response as evidence; do not let the provider's
            # second cache return it again after the stage receipt rejects it.
            provider.rename(provider.with_name(provider.stem+'.rejected-'+str(time.time_ns())+'.json'))

    def json(self, system, data, schema, **kwargs):
        if system.startswith('Audit publishing copy') and isinstance(data,dict) and 'draft' in data and 'speech' in data:
            from .prepare_post_audit import citation_audit
            return citation_audit(self,data)
        if getattr(self, 'bounded_selection', False):
            # Selection schemas already contain bounded scores/reasons. Spending
            # the response budget on hidden reasoning can truncate the JSON.
            kwargs['think'] = False
        guard = vars(self.brain).get('request_guard')
        if guard is not None:
            data = guard.prepare(system, data, schema, kwargs)
        request = {'model': self.name, 'system': system, 'input': data, 'schema': schema,
                   'creator_context': self.context, 'options': kwargs}
        if guard is not None:
            request['final_input_sha256'] = guard.preflight['payload_sha256']
        key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        target = self.folder / ('model-' + key + '.json')
        if target.is_file():
            saved = json.loads(target.read_text('utf-8'))
            if saved.get('status') == 'complete':
                saved['cache_hits'] = saved.get('cache_hits', 0) + 1
                write(target, saved)
                result=saved['result'];self._receipt_paths[id(result)]={target}
                for name in saved.get('response_receipts',[]):
                    if isinstance(name,str) and Path(name).name==name and name.startswith('model-') and name.endswith('.json'):
                        self._receipt_paths[id(result)].add(self.folder/name)
                provider=saved.get('provider_cache_file')
                if isinstance(provider,str):self._provider_cache_paths[id(result)]=Path(provider)
                return result
            if (saved.get('status') == 'failed' and
                    'does not match the expected peg-native format' in str(saved.get('error', '')) and
                    not getattr(self, '_format_retry', False)):
                # Resume directly with the recorded correction instead of
                # spending another full inference on the identical failed call.
                self._format_retry = True
                try:
                    return self.json(system, {**data,
                        'previous_format_error': saved['error'][:700],
                        'format_correction': 'Return one complete JSON object matching the schema. Keep strings short; no reasoning or prose outside JSON.'},
                        schema, **{**kwargs, 'think': False, 'max_tokens': min(3200, kwargs.get('max_tokens', 1800) + 800)})
                finally:
                    self._format_retry = False
        receipt = {'provider': 'ollama', 'model': self.name, 'system': system,
                   'input': data, 'schema': schema, 'creator_context': self.context,
                   'options': kwargs, 'intervention': False, 'status': 'started', 'request_sha256': key}
        if guard is not None:receipt['preflight_budget'] = guard.preflight
        write(target, receipt)
        try:
            if guard is not None:guard.last = None
            result = self.brain.json(system, data, schema, **kwargs)
            self._receipt_paths[id(result)]={target}
            provider=getattr(self.brain,'last_cache_file',None)
            if isinstance(provider,Path):
                self._provider_cache_paths[id(result)]=provider;receipt['provider_cache_file']=str(provider)
            receipt.update(status='complete', result=result, usage=getattr(self.brain, 'last_usage', {}))
            if guard is not None and guard.last is not None:receipt['request_budget'] = guard.last
            return result
        except Exception as error:
            from hinglish_app.user_messages import diagnostics
            receipt.update(status='failed', error=diagnostics(error))
            format_failure = (isinstance(error, json.JSONDecodeError) or
                isinstance(error, RuntimeError) and any(marker in str(error) for marker in
                    ('required structured answer', 'does not match the expected peg-native format')))
            if format_failure:
                if isinstance(error,json.JSONDecodeError):receipt['malformed_response'] = error.doc[:20000]
                write(target, receipt)
                if not getattr(self, '_format_retry', False):
                    self._format_retry = True
                    try:
                        repaired = self.json(system, {**data, 'previous_format_error': diagnostics(error)[:700], 'format_correction':
                            'Return one complete JSON object matching the schema. Keep strings short; no reasoning or prose outside JSON.'},
                            schema, **{**kwargs, 'think': False, 'max_tokens': min(3200, kwargs.get('max_tokens', 1800) + 800)})
                        receipt.update(status='complete', result=repaired, format_recovery=True)
                        self._receipt_paths.setdefault(id(repaired),set()).add(target)
                        receipt['response_receipts']=[p.name for p in self._receipt_paths[id(repaired)]]
                        if id(repaired) in self._provider_cache_paths:
                            receipt['provider_cache_file']=str(self._provider_cache_paths[id(repaired)])
                        return repaired
                    finally:
                        self._format_retry = False
            raise
        finally:
            write(target, receipt)


class LocalRuntime:
    def __init__(self, root):
        self.root = Path(root)

    def stage(self, stage, draft, progress):
        from hinglish_niche.profiles import Profiles, use
        folder = self.root / 'output/publisher-prepare-post/preparations' / draft['id']
        folder.mkdir(parents=True, exist_ok=True)
        context = Profiles(self.root).context(draft['profile'])
        write(folder / 'creator-context.json', context)
        with use(context):
            result = self._stage(stage, draft, folder, context, progress)
        write(folder / (stage.replace(':', '-') + '.json'), result)
        return result

    def _stage(self, stage, draft, folder, context, progress):
        from hinglish_shorts.source import open_video
        video = open_video(draft['source']['path'])
        stages = draft['stages']
        if stage == 'inspect':
            return {'duration': video.duration, 'width': video.width, 'height': video.height}
        if stage == 'speech':
            from hinglish_shorts.source import transcribe
            from .memory import correct_words
            device = inference_device(self.root)
            progress('Starting speech recognition on ' + ('GPU (CUDA)' if device == 'cuda' else 'CPU'))
            words = transcribe(self.root, video, device=device, progress=progress,
                               skip_invalid_recognition=draft['profile'] == 'gaming', retry_unreadable=True,
                               cache_namespace=draft['id'] if draft.get('fresh_start') else None)
            words, changes = correct_words(self.root, words)
            if not words:
                raise ValueError('No usable speech was found. Choose a source with clear spoken content.')
            return {'words': [[w.text, w.start, w.end] for w in words],
                    'transcript': ' '.join(w.text for w in words), 'corrections': changes,
                    'source': draft['source'], 'tool': 'Storylens local transcription', 'device': device}
        from hinglish_cut.model import Word
        words = [Word(*w) for w in stages['speech']['words']]
        if stage.startswith('copy:instagram:'):
            n = int(stage.split(':')[2])
            paired = stages.get(f'copy:youtube:{n}', {}).get('paired_instagram')
            output = stages.get(f'render:{n}')
            if paired and output and paired.get('source_sha256') == output['video']['sha256']:
                verify_identity(output['video'])
                from .prepare_post_source import short_instagram, validate_caption_acronyms
                try:
                    short_instagram(paired['metadata']['instagram_caption'])
                    validate_caption_acronyms(paired['metadata']['instagram_caption'],output['transcript'])
                    return {**paired, 'reused_paired_copy': True}
                except ValueError:
                    pass  # Older paired paragraphs must be rewritten to the new owner limit.
        if stage in ('selection', 'highlight-selection') or stage.startswith(('copy:', 'context:', 'discovery:', 'weekly:')):
            from hinglish_visuals.brain import open_brain
            from hinglish_cut.model_preferences import preferences
            model=preferences(self.root).get('publishing_model','qwen3:8b')
            if stage.startswith(('discovery:', 'weekly:')) or stage.startswith('copy:') and draft.get('discovery_review'):
                from .weekly_seo_plan import V8_MODEL
                model=V8_MODEL  # Owner explicitly rejected V14 for these workflows.
            brain = open_brain(self.root, 'ollama', model=model, progress=progress)
            from .test_mode import enabled as repeat_uploads
            if repeat_uploads(self.root, draft['profile']):
                brain.cache_enabled = False  # This test must measure new inference, not old global answers.
            recorded = RecordedBrain(brain, folder, context)
            from hinglish_visuals.brain import OllamaBrain
            if isinstance(brain, OllamaBrain):
                from .prepare_post_budget import PublishingBudget
                brain.request_guard = PublishingBudget(self.root, brain, folder, recorded, progress)
            try:
                if stage.startswith('context:'):
                    text = stages.get('highlights', stages['speech'])['transcript']
                    number = int(stage.split(':')[1])
                    excerpt = text_chunks(text)[number - 1]
                    from .prepare_post_source import source_quotes
                    return source_quotes(recorded, excerpt, number, folder, progress)
                if stage == 'selection':
                    from hinglish_shorts.find import find_shorts
                    from hinglish_shorts.settings import ShortsSettings
                    settings = ShortsSettings(count=str(draft['count']), brain='ollama', device=inference_device(self.root), captions=False)
                    recorded.bounded_selection = True
                    clips, summary, _ = find_shorts(recorded, words, settings, progress, source_duration=video.duration)
                    return {'clips': [{'index': n + 1, **clip.to_dict()} for n, clip in enumerate(clips)],
                            'summary': summary, 'model': brain.name, 'requested_count': draft['count']}
                if stage == 'highlight-selection':
                    from hinglish_niche.gaming import candidates, select
                    moments = select(candidates(recorded, words, video.duration, stages['highlight-signals'], progress), draft['minutes'] * 60)
                    if not moments:
                        raise ValueError('No complete gaming highlights were found. Choose a source with clear gameplay commentary.')
                    return {'moments': moments, 'model': brain.name, 'target_minutes': draft['minutes']}
                _, platform, number = stage.split(':')
                n = int(number)
                output = stages[f'render:{n}'] if draft['mode'] == 'shorts' else stages.get('highlights')
                if output:
                    verify_identity(output['video'])
                transcript = output['transcript'] if output else stages['speech']['transcript']
                chunks = text_chunks(transcript)
                if len(chunks) > 1:
                    from .prepare_post_source import source_quotes
                    # Old free-form summaries stay in their saved stage/receipts.
                    # They are never used as evidence for new publishing copy.
                    quotes = [source_quotes(recorded, chunk, i, folder, progress) for i, chunk in enumerate(chunks, 1)]
                    transcript = '\n'.join(quote for section in quotes for quote in section['facts'])
                if len(transcript) > 24000 and vars(brain).get('request_guard') is None:
                    raise ValueError('This source has too many topics for one metadata pass. Keep its summaries and choose a shorter finished source.')
                from . import metadata
                from .memory import CreatorMemory
                from .prepare_post_source import INSTAGRAM_PROPERTIES, INSTAGRAM_SCHEMA, INSTAGRAM_FORMAT, instagram_from_words
                data = {'spoken_content': transcript, 'source_method': 'verbatim_source_quotes_v2', 'creator_profile': context,
                        'writing_preferences': CreatorMemory(self.root, draft['profile']).writing_context()}
                if stage.startswith('weekly:'):
                    from .weekly_seo_plan import generate
                    return {'weekly_seo':generate(recorded,self.root,transcript,
                        stages[f'copy:youtube:{n}']['metadata'],context,data['writing_preferences'],
                        draft['weekly_weeks'],progress)}
                if stage.startswith('discovery:'):
                    if platform != 'youtube':
                        raise ValueError('Choose a prepared YouTube video for this SEO review.')
                    from .discovery import attach
                    return attach(self.root, stages[f'copy:youtube:{n}'], recorded, transcript, context,
                                  data['writing_preferences'], {**draft, 'discovery_review': True}, progress)
                if platform == 'youtube':
                    schema = {**metadata.SCHEMA, 'properties': {k: metadata.SCHEMA['properties'][k] for k in ('title', 'description', 'tags')}, 'required': ['title', 'description', 'tags']}
                    system = ('Write YouTube title, description and tags from the supplied speech excerpts. Return JSON. '
                              'Focus on the supported central story and themes. Do not join a year, score or winner from different statements into a new event. '
                              'Omit uncertain statistics and garbled names instead of filling them from memory. Historical footage is a retrospective. '
                              + metadata.CONTENT_RULE + metadata.ENGLISH_RULE + metadata.SEO_RULE)
                    if draft['mode'] == 'shorts':
                        schema = {**schema,'properties':{**schema['properties'],**INSTAGRAM_PROPERTIES},
                                  'required':schema['required']+list(INSTAGRAM_PROPERTIES)}
                        system += ' In this same response, also prepare distinct Instagram text. '+INSTAGRAM_FORMAT
                else:
                    schema = INSTAGRAM_SCHEMA
                    system = 'Write a short, natural English Instagram caption. Use only the supported central topic. '+INSTAGRAM_FORMAT+' '+metadata.CONTENT_RULE+metadata.ENGLISH_RULE
                for attempt in range(3 if platform == 'instagram' else 2):
                    progress(f'Writing {platform} copy for video {n}' + ('; correcting the saved issue' if attempt else ''))
                    answer = None
                    try:
                        answer = recorded.json(system, data, schema, max_tokens=1800, think=False)
                        value = answer
                        if platform == 'instagram' or draft['mode'] == 'shorts':
                            value={**value,'instagram_caption':instagram_from_words(value)}
                        if platform == 'youtube':
                            value = metadata.normalize_source_hashtags(metadata.normalize_youtube_hashtags(metadata.validate({**value, 'instagram_caption': value.get('instagram_caption','')})), transcript)
                            if not 3 <= value['description'].count('#') <= 5:
                                raise ValueError('End the description with 3-5 relevant hashtags.')
                            metadata.validate_source_copy(value, transcript)
                            if draft['mode'] == 'shorts':
                                from .prepare_post_source import short_instagram
                                caption = short_instagram(value['instagram_caption'])
                                value['instagram_caption']=caption
                                metadata.validate_source_copy({'description':caption},transcript)
                        else:
                            from .prepare_post_source import short_instagram
                            caption = short_instagram(value.get('instagram_caption',''))
                            import re
                            tags = re.findall(r'#([A-Za-z0-9_]+)', caption)
                            value = {'instagram_caption': caption, 'title': caption.splitlines()[0][:100],
                                     'description': caption, 'tags': tags}
                            metadata.validate_source_copy(value,transcript)
                        if platform == 'instagram' or draft['mode'] == 'shorts':
                            from .prepare_post_source import validate_caption_acronyms
                            validate_caption_acronyms(value['instagram_caption'],transcript)
                        metadata.review_grounding(recorded, value, transcript)
                        result = {'metadata': value, 'model': brain.name, 'provider': 'ollama', 'source_sha256': (output['video'] if output else draft['source'])['sha256']}
                        if platform == 'youtube' and draft['mode'] == 'shorts':
                            import re
                            caption = value['instagram_caption']
                            result['paired_instagram'] = {**{k:v for k,v in result.items() if k!='metadata'},
                                'metadata': {'instagram_caption':caption,'title':caption.splitlines()[0][:100],
                                             'description':caption,'tags':re.findall(r'#([A-Za-z0-9_]+)',caption)}}
                        if platform == 'youtube':
                            from .discovery import attach
                            result = attach(self.root, result, recorded, transcript, context,
                                            data['writing_preferences'], draft, progress)
                        return result
                    except (ValueError, TypeError) as error:
                        if answer is not None:recorded.reject_result(answer,error)
                        data['correction'] = str(error)
                        data.setdefault('corrections',[]).append(str(error))
                if platform == 'youtube':
                    from .prepare_post_source import recover_youtube
                    value = recover_youtube(recorded, transcript, folder, context,
                                            data['writing_preferences'], progress)
                    result = {'metadata': value, 'model': brain.name, 'provider': 'ollama',
                            'copy_method': 'checked_concise_recovery',
                            'source_sha256': (output['video'] if output else draft['source'])['sha256']}
                    from .discovery import attach
                    return attach(self.root, result, recorded, transcript, context,
                                  data['writing_preferences'], draft, progress)
                if platform == 'instagram' and stages.get(f'copy:youtube:{n}'):
                    from .prepare_post_source import recover_instagram
                    value = recover_instagram(recorded, stages[f'copy:youtube:{n}']['metadata'], transcript,
                                               context, data['writing_preferences'], progress)
                    return {'metadata':value,'model':brain.name,'provider':'ollama','copy_method':'checked_caption_recovery',
                            'source_sha256':(output['video'] if output else draft['source'])['sha256']}
                raise ValueError('The local model could not finish reliable copy. Resume this copy stage; the prepared videos are saved.')
            finally:
                brain.close()
        if stage == 'highlight-signals':
            from hinglish_niche.gaming import signals
            return signals(self.root, video, progress)
        if stage.startswith('render:'):
            n = int(stage.split(':')[1])
            clip = stages['selection']['clips'][n - 1]
            pieces = clip['pieces']
            target = self._render(video.path, pieces, folder / f'clip-{n:02d}', portrait=True, progress=progress)
        elif stage == 'highlights':
            pieces = [[m['start'], m['end']] for m in stages['highlight-selection']['moments']]
            target = self._render(video.path, pieces, folder / 'highlights', portrait=False, progress=progress)
        else:
            raise ValueError('This preparation stage is unsupported. Check the saved stage details.')
        facts = open_video(target)
        if facts.duration <= 0 or stage.startswith('render:') and (facts.height <= facts.width or facts.duration > 180):
            raise ValueError('The rendered clip does not meet the required duration or portrait format. Retry this clip.')
        text = ' '.join(w.text for w in words if any(a <= (w.start + w.end) / 2 < b for a, b in pieces))
        if not text:
            raise ValueError('This clip has no selected spoken context. Check its saved selection before retrying.')
        return {'video': file_identity(target), 'transcript': text, 'pieces': pieces,
                'duration': facts.duration, 'width': facts.width, 'height': facts.height,
                'source': draft['source'], 'tool': 'FFmpeg', 'thumbnail': None}

    def _render(self, source, pieces, folder, *, portrait, progress):
        """Reuse each verified segment after interruption; never makes thumbnails."""
        from imageio_ffmpeg import get_ffmpeg_exe
        from hinglish_shorts.source import open_video
        from hinglish_cut.compute_policy import ffmpeg_h264, heavy_device
        encoding = ffmpeg_h264(heavy_device(self.root), quality=20)
        folder.mkdir(parents=True, exist_ok=True)
        source_stamp = file_identity(source)
        exe = get_ffmpeg_exe()
        files = []
        for n, (start, end) in enumerate(pieces, 1):
            if not 0 <= start < end:
                raise ValueError('The selected interval is invalid. Check the saved clip plan.')
            path = folder / f'part-{n:03d}.mp4'
            receipt = folder / f'part-{n:03d}.json'
            expected = {'source': source_stamp, 'start': start, 'end': end, 'portrait': portrait}
            reused = False
            if receipt.is_file() and path.is_file():
                saved = json.loads(receipt.read_text('utf-8'))
                if saved.get('intent') == expected:
                    verify_identity(saved['file'])
                    reused = True
            if not reused:
                progress(f'Rendering saved interval {n}/{len(pieces)}')
                size = '720:1280' if portrait else '1280:720'
                partial = path.with_suffix('.partial.mp4')
                command = [exe, '-y', '-v', 'error', '-threads', '2', '-ss', str(start), '-i', source,
                           '-t', str(end - start), '-map', '0:v:0', '-map', '0:a:0',
                           '-vf', f'scale={size}:force_original_aspect_ratio=decrease,pad={size}:(ow-iw)/2:(oh-ih)/2,setsar=1',
                           '-r', '30', *encoding, '-threads', '2',
                           '-c:a', 'aac', '-ac', '2', '-ar', '48000', '-movflags', '+faststart', str(partial)]
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if abs(open_video(partial).duration - (end - start)) > 1:
                    raise ValueError('A rendered interval is incomplete. Resume to retry this interval.')
                partial.replace(path)
                write(receipt, {'intent': expected, 'file': file_identity(path), 'command': command})
            files.append(path)
        playlist = folder / 'concat.txt'
        playlist.write_text('\n'.join("file '" + p.name + "'" for p in files), encoding='utf-8')
        target = folder / 'finished.mp4'
        partial = folder / 'finished.partial.mp4'
        subprocess.run([exe, '-y', '-v', 'error', '-f', 'concat', '-safe', '1', '-i', str(playlist),
                        '-c', 'copy', '-movflags', '+faststart', str(partial)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if abs(open_video(partial).duration - sum(b - a for a, b in pieces)) > max(1, len(pieces) * .1):
            raise ValueError('The assembled video is incomplete. Resume assembly; rendered intervals are saved.')
        partial.replace(target)
        return target
