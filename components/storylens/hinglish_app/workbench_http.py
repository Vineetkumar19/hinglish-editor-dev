"""Authenticated local-workbench routes with private result paths."""
from pathlib import Path
from urllib.parse import parse_qs
import json
import mimetypes
import secrets

from .workbench_jobs import service


def get(handler,state,parsed):
    query=parse_qs(parsed.query)
    media_token=parsed.path in ('/api/workbench/slow-motion-media','/api/workbench/media','/api/workbench/intro-media','/api/workbench/sound-media','/api/workbench/mix-media','/api/workbench/assembly-media','/api/workbench/documentary-media','/api/workbench/source-preview','/api/workbench/native-preview','/api/workbench/hook-media','/api/workbench/match-cut-media','/api/workbench/gaming-intro-media') and secrets.compare_digest(query.get('token',[''])[0],state.token)
    if not handler._authorized() and not media_token:return handler._json(403,{'error':'Not connected'})
    if parsed.path == '/api/workbench/slow-motion-media':
        from .selective_slow_motion_http import media
        return media(handler, service(state), query)
    if parsed.path.rsplit('/',1)[-1] in ('sounds','sound-media','mix-media'):
        from .sound_http import get as sound_get
        return sound_get(handler,state,parsed.path,query)
    if parsed.path.endswith(('/hook-drafts','/hook-media')):
        from .hook_drafts import get_draft
        return get_draft(handler,state,parsed.path,query)
    if parsed.path.endswith('/documentary-media'):
        from .documentary_service import database
        from hinglish_cinematic.curation import file_hash
        record=database(state).get(query.get('id',[''])[0])
        if not record.get('documentary'):raise ValueError('Choose an imported documentary.')
        file=Path(record['source']['path'])
        if not file.is_file() or file.stat().st_size!=record['source'].get('size',file.stat().st_size):raise ValueError('The documentary source changed.')
        return _media(handler,file,False)
    if parsed.path.endswith('/reference-styles'):
        from .curation_http import store
        return handler._json(200, {'cards':store(state).list('reference-style')})
    if parsed.path.endswith('/curation-search'):
        from .curation_http import snapshot
        from hinglish_cinematic.media_index import normalize_search_filters, search_clips
        data=snapshot(state,query.get('id',[''])[0])
        filters=normalize_search_filters({key:values[0] for key,values in query.items()})
        return handler._json(200, {'results': search_clips(data['candidates'], query.get('q', [''])[0], filters=filters, limit=100)})
    if parsed.path.endswith('/template-assets'):
        from .library_assets import catalogue
        return handler._json(200,{'packs':catalogue(query.get('section',[''])[0])})
    if parsed.path.endswith('/grade-luts'):
        from .library_assets import luts
        return handler._json(200,luts())
    if parsed.path.endswith('/grade-lut-file'):
        from .library_assets import lut_file
        return _media(handler,lut_file(query.get('id',[''])[0]),True)
    if parsed.path.endswith('/grade-template'):
        from .resolve_grade import template
        file=template();data=file.read_bytes()
        handler.send_response(200);handler.send_header('Content-Type','application/octet-stream');handler.send_header('Content-Disposition','attachment; filename="Storylens SDR nodes.drx"');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data);return
    if parsed.path.endswith('/trial-review'):
        from .trial_review import read
        return handler._json(200, read(state, query.get('id', [''])[0], int(query.get('variant', ['-1'])[0])))
    if parsed.path.endswith('/intro-plan'):
        from hinglish_cinematic.curation import Store
        plan=Store(state.root/'cache/curation/projects.sqlite3').get(query.get('id',[''])[0])
        if plan.get('kind')!='intro':raise ValueError('Choose a saved intro plan.')
        return handler._json(200,plan)
    if parsed.path.endswith('/preselection-gate'):
        from .curation_http import preselection_gate
        return handler._json(200, preselection_gate(state))
    if parsed.path.endswith('/curation'):
        from .curation_http import snapshot
        return handler._json(200,snapshot(state,query.get('id',[''])[0]))
    if parsed.path.endswith('/curation-datasets'):
        import json
        rows=[]
        for file in sorted((state.root/'output/workbench').glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:row=json.loads(file.read_text('utf-8'))
            except (ValueError,OSError):continue
            if row.get('kind')=='footage' and row.get('status')=='complete':
                rows.append({'id':row['id'],'name':Path(row['request'].get('folder') or row['id']).name+' · '+row['id'][:8]})
            if len(rows)>=20:break
        return handler._json(200,{'datasets':rows})
    job=service(state).snapshot(query.get('id',[''])[0])
    if parsed.path == '/api/workbench/gaming-intro-media':
        if job['kind'] != 'gaming-intro' or job['status'] != 'complete':
            raise ValueError('Choose a completed gaming intro.')
        asset = 'timeline' if query.get('asset') == ['timeline'] else 'video'
        file = Path(job['result'][asset]).resolve()
        if not file.is_relative_to((state.root/'output/workbench'/job['id']).resolve()) or not file.is_file():
            raise ValueError('The saved gaming intro file is unavailable.')
        return _media(handler,file,asset == 'timeline' or query.get('download') == ['1'])
    if parsed.path.endswith('/match-cut-result'):
        if job['kind'] != 'match-cut' or job['status'] != 'complete':
            raise ValueError('Choose a completed Match Cut Finder result.')
        from hinglish_cinematic.match_cut import snapshot
        return handler._json(200, snapshot(state.root, job['result']['project']))
    if parsed.path.endswith('/match-cut-media'):
        if job['kind'] != 'match-cut' or job['status'] != 'complete':
            raise ValueError('Choose a completed Match Cut Finder result.')
        from hinglish_cinematic.match_cut import _project, snapshot
        result = snapshot(state.root, job['result']['project'])
        asset = result['artifacts'].get(query.get('asset', [''])[0])
        if not asset:
            raise ValueError('Choose a video from this match result.')
        folder = _project(state.root, result['project'])
        path = (folder / asset['path']).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError('This match export is unavailable. Check its output folder.')
        return _media(handler, path, query.get('download') == ['1'])
    if parsed.path.endswith('/native-preview'):
        if job['kind']!='native-curation' or job['status']!='complete' or job['request']['action']!='render':raise ValueError('Wait for the native preview to finish.')
        file=Path(job['result']['preview_path']).resolve()
        if not file.is_relative_to((state.root/'output/workbench'/job['id']).resolve()):raise ValueError('The native preview is unavailable.')
        return _media(handler,file,False)
    if parsed.path.endswith('/source-preview'):
        if job['kind']!='source-proxy' or job['status']!='complete':raise ValueError('Wait for the source preview.')
        part='strip' if query.get('kind')==['strip'] else 'path'
        file=Path(job['result'][part]).resolve()
        if not file.is_relative_to((state.root/'cache/curation/proxies').resolve()) or not file.is_file():raise ValueError('This preview is unavailable.')
        return _media(handler,file,False)
    if parsed.path.endswith('/assembly-media'):
        if job['status']!='complete' or job['kind'] not in ('body','trials'):raise ValueError('Choose a completed body or trial.')
        part=query.get('part',['body'])[0]
        if part=='body':artifact=job['result'] if job['kind']=='body' else job['result']['body']
        else:
            if job['kind']!='trials' or part not in ('0','1','2'):raise ValueError('Choose one of the three trials.')
            artifact=job['result']['trials'][int(part)]
        file=Path(artifact['path']).resolve()
        if not file.is_relative_to((state.root/'output/workbench').resolve()):raise ValueError('This assembly is unavailable.')
        return _media(handler, file, query.get('download') == ['1'])
    if parsed.path.endswith('/intro-media'):
        if job['kind'] not in ('intro','intro-sound') or job['status']!='complete':raise ValueError('Choose a completed intro preview.')
        index=int(query.get('variant',['-1'])[0]);rows=job['result']['intros']
        if not 0<=index<len(rows):raise ValueError('Choose one of this job’s intro variants.')
        file=Path(rows[index]['path']).resolve()
        if not file.is_relative_to((state.root/'output/workbench').resolve()):raise ValueError('The intro preview is unavailable.')
        return _media(handler,file,False)
    if parsed.path.endswith('/job'):return handler._json(200,job)
    if parsed.path.endswith('/media'):
        if query.get('kind')==['contact-sheet']:
            name=query.get('sheet',[''])[0]
            review=(job.get('result') or {}).get('review',{})
            if job['kind']!='footage' or job['status']!='complete' or not any(row['file']==name for row in review.get('sheets',[])):
                raise ValueError('Choose a contact sheet from this completed footage scan.')
            directory=(state.root/'output/workbench'/job['id']/'Best Clip'/'Review').resolve()
            file=(directory/name).resolve()
            if file.parent!=directory or not file.is_file():raise ValueError('The contact sheet is unavailable.')
            return _media(handler,file,False)
        assets=(job.get('result') or {}).get('assets',[])
        item=next((a for a in assets if a['id']==query.get('asset',[''])[0]),None)
        if not item:raise ValueError('Choose a saved footage clip.')
        thumbnail=query.get('kind')==['poster']
        file=Path(item['poster'] if thumbnail else item['path']).resolve()
        if not file.is_relative_to((state.root/'output/workbench'/job['id']).resolve()) or not file.is_file():raise ValueError('The footage clip is unavailable.')
        if thumbnail:
            data=file.read_bytes();handler.send_response(200);handler.send_header('Content-Type','image/jpeg');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data);return
        # Reuse the existing bounded Range implementation for video playback.
        return _media(handler,file,query.get('download')==['1'])
    raise ValueError('Choose a supported workbench result.')


def _media(handler,path,download):
    import re
    size=path.stat().st_size;start,end=0,size-1;requested=handler.headers.get('Range')
    if requested:
        match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
        if not match or int(match[1])>=size or (match[2] and int(match[2])<int(match[1])):
            handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.send_header('Content-Length','0');handler.end_headers();return
        start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
    handler.send_response(206 if requested else 200);handler.send_header('Content-Type',mimetypes.guess_type(str(path))[0] or 'application/octet-stream');handler.send_header('Content-Length',str(end-start+1));handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','no-store')
    if download:handler.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
    if requested:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    with path.open('rb') as file:
        file.seek(start);remaining=end-start+1
        while remaining:
            data=file.read(min(256*1024,remaining))
            if not data:break
            try:handler.wfile.write(data)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):break
            remaining-=len(data)


def post(handler,state,path,value):
    from .editor_panel import ensure_license
    host=value.get('host','standalone')
    if host not in ('standalone','aftereffects','premiere'):raise ValueError('Choose a connected Storylens editor.')
    ensure_license(state,host)
    if path=='/api/workbench/grade-lut-preview':
        from .resolve_grade import preview_lut
        return handler._json(200,preview_lut(state.root,value))
    if path.endswith('/library-reveal'):
        from .library_assets import reveal
        return handler._json(200,reveal(value.get('section'),value.get('id')))
    if path.rsplit('/',1)[-1] in ('sound-inspect','sound-import','sound-review','sound-plan','sound-render'):
        from .sound_http import post as sound_post
        with state.work_lock:return sound_post(handler,state,path,value)
    if path.rsplit('/',1)[-1] in ('body-render','trials-render'):
        from .assembly_service import request
        return handler._json(202,request(state,value,'body' if path.endswith('/body-render') else 'trials'))
    if path.rsplit('/',1)[-1] in ('documentary-inspect','documentary-import','documentary-graph'):
        from .documentary_service import inspect_inputs,import_body,save_graph
        with state.work_lock:
            result=inspect_inputs(value) if path.endswith('/documentary-inspect') else import_body(state,value) if path.endswith('/documentary-import') else save_graph(state,value)
            return handler._json(200,result)
    if path.rsplit('/',1)[-1] in ('reference-inspect','reference-style','reference-pattern-review'):
        from .reference_style import inspect_reference, save_card, review_pattern
        if path.endswith('/reference-inspect'):
            return handler._json(200,inspect_reference(value))
        with state.work_lock:
            result=save_card(state,value) if path.endswith('/reference-style') else review_pattern(state,value)
            return handler._json(200,result)
    if path == '/api/workbench/gaming-intro':
        from .gaming_intro import request
        return handler._json(202,service(state).start('gaming-intro',request(value)))
    if path.endswith('/hook-export'):
        from .hook_drafts import prepare_export
        return handler._json(200,prepare_export(state.root,value.get('editor'),value.get('draft')))
    if path.endswith('/hook-precomps'):
        from .hook_drafts import download_precomps
        return download_precomps(handler,state,value)
    if path.endswith('/curation'):
        from .curation_http import command
        with state.work_lock:
            return handler._json(200,command(state,value))
    if path.endswith('/trial-review'):
        from .trial_review import save
        with state.work_lock:
            return handler._json(200, save(state, value))
    if path.endswith('/intro-plan'):
        from .intro_service import create
        return handler._json(200,create(state,value))
    if path.endswith('/replace-intro'):
        from .intro_service import replace_variant
        with state.work_lock:
            return handler._json(202, replace_variant(state, value))
    if path.endswith('/intro-render'):
        from .intro_service import render
        return handler._json(202,render(state,value))
    jobs=service(state)
    if path.startswith('/api/workbench/slow-motion-'):
        from .selective_slow_motion_http import post as slow_motion_post
        with state.work_lock:
            return slow_motion_post(handler, jobs, path.rsplit('/', 1)[-1], value)
    if path.rsplit('/',1)[-1] in ('native-slot-proposal','native-slot-map'):
        from hinglish_cinematic.native_slot_plan import propose_slots
        from hinglish_cinematic.curation import Store,file_hash
        inspected=jobs.snapshot(value['inspection_id'])
        if inspected['kind']!='native-curation' or inspected['status']!='complete' or inspected['request']['action']!='inspect':raise ValueError('Inspect the native template first.')
        manifest_path=Path(inspected['result']['manifest_path'])
        if file_hash(manifest_path)!=inspected['result']['manifest_hash']:raise ValueError('The template manifest changed; inspect it again.')
        bank=Store(state.root/'cache/curation/projects.sqlite3').get(value['dataset_id'])
        if bank['revision']!=value['expected_revision']:raise ValueError('Reload the current footage review.')
        manifest=json.loads(manifest_path.read_text('utf-8-sig'))
        if path.endswith('/native-slot-proposal'):
            if not manifest['supported']:raise ValueError('This template cannot be populated. Export the slot map for manual review.')
            return handler._json(200,propose_slots(manifest,bank))
        candidates={row['id']:row for row in bank['candidates']}
        valid_slots={slot['slot_id'] for slot in manifest['slots']}
        banned=set((bank.get('body') or {}).get('banned',[]))
        choices={}
        for assignment in value.get('assignments',[]):
            slot_id=assignment.get('slot_id')
            candidate_id=assignment.get('candidate_id')
            if slot_id not in valid_slots or slot_id in choices:
                raise ValueError('Each reviewed assignment must identify a different inspected slot.')
            if candidate_id and (candidate_id not in candidates or candidate_id in banned):
                raise ValueError('A selected candidate is unavailable for this slot map.')
            choices[slot_id]=candidates.get(candidate_id)
        slots=[]
        for slot in manifest['slots']:
            candidate=choices.get(slot['slot_id'])
            if candidate is not None and candidate['review_state']!='approved':
                raise ValueError('Choose reviewed and approved candidates for the slot map.')
            source={key:candidate.get(key) for key in ('id','source_id','source','in_pts','out_pts','timebase','quality_signals','duplicate_group','phase_tags')} if candidate else None
            slots.append({**slot,'candidate':source,'assignment_state':'proposed' if source else 'unassigned'})
        return handler._json(200,{'version':1,'approval_state':'manual_review','template_supported':manifest['supported'],
            'unsupported':manifest.get('unsupported',[]),'manifest_hash':inspected['result']['manifest_hash'],
            'template_project':manifest['project_path'],'footage_bank_id':bank['id'],'body_revision':bank['revision'],
            'slots':slots})
    if path.endswith('/intro-sound'):
        from .intro_sound import prepare
        with state.work_lock:return handler._json(202,jobs.start('intro-sound',prepare(state,value)))
    if path.endswith('/native-curation'):
        from .native_curation import prepare
        with state.work_lock:return handler._json(202,jobs.start('native-curation',prepare(state,value)))
    if path.endswith('/sound-loop'):
        from hinglish_cinematic.curation import Store, resolve_sound
        from hinglish_cinematic.sound_loop import loop_settings
        catalog=Store(state.root/'cache/curation/projects.sqlite3').list('sound')
        asset=resolve_sound(catalog,value['asset_id'],value['source_hash'])
        if '03_Ambience' not in asset['categories'] or asset.get('derivation'):
            raise ValueError('Choose an approved original ambience recording.')
        return handler._json(202,jobs.start('sound-loop',{
            'asset_id':asset['id'],'source_hash':asset['hash'],'idempotency_key':value['idempotency_key'],
            **loop_settings(value,asset),
        }))
    if path.endswith('/source-proxy'):return handler._json(202,jobs.start('source-proxy',value))
    if path.endswith('/visual-index'):return handler._json(202,jobs.start('visual-index',value))
    if path.endswith('/match-cut-review'):
        from hinglish_cinematic.match_cut import review
        with state.work_lock:
            result = review(state.root, value)
        if value.get('action') == 'insert_group' and value.get('download') is True:
            return _media(handler, Path(result['timeline']), True)
        return handler._json(200, result)
    if path.endswith('/match-cut'):
        if value.get('dataset_id'):
            footage = jobs.snapshot(value['dataset_id'])
            if footage['kind'] != 'footage' or footage['status'] != 'complete':
                raise ValueError('Choose a completed Cinematic Footage collection.')
            request = footage['request']
            paths, folders = value.get('paths', []), value.get('folders', [])
            if not isinstance(paths, list) or not isinstance(folders, list):
                raise ValueError('Choose a video list or folder list.')
            value = {**value, 'paths': paths + request.get('paths', []),
                     'folders': folders + ([request['folder']] if request.get('folder') else [])}
        return handler._json(202, jobs.start('match-cut', value))
    if path.endswith('/footage'):return handler._json(202,jobs.start('footage',value))
    if path.endswith('/color-grade'):return handler._json(202,jobs.start('color-grade',value))
    if path.endswith('/resume'):return handler._json(202,jobs.resume(value.get('id','')))
    if path.endswith('/cancel'):return handler._json(200,jobs.cancel(value.get('id','')))
    if path.endswith('/open'):
        import os
        job=jobs.snapshot(value.get('id',''));folder=jobs._file(job['id']).parent
        if job['kind'] == 'match-cut' and job['status'] == 'complete':
            from hinglish_cinematic.match_cut import _project
            folder = _project(state.root, job['result']['project'])
        if not folder.is_dir():raise ValueError('This output folder is unavailable.')
        os.startfile(str(folder));return handler._json(200,{'ok':True})
    raise ValueError('Choose a supported workbench action.')
