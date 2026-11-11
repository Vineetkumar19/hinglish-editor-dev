"""Authenticated local APIs shared by the Adobe panels and CapCut companion."""
from pathlib import Path
from urllib.parse import parse_qs
import mimetypes
import secrets
import hashlib
from .editor_panel import panel_service,prepare_import,ensure_license,HOSTS,TOOLS


def get(handler,state,parsed):
    query=parse_qs(parsed.query);media=parsed.path in ('/api/panel/media','/api/panel/visual-source-media','/api/panel/sound-audition-media','/api/panel/image-file')
    if not handler._authorized() and not (media and secrets.compare_digest(query.get('token',[''])[0],state.token)):
        return handler._json(403,{'error':'Reopen this panel from the local editor to connect.'})
    if parsed.path in ('/api/panel/template-text-job','/api/panel/template-text-plan'):
        from .template_text import service
        jobs=service(state.root);key=query.get('id',[''])[0]
        return handler._json(200,jobs.plan(key) if parsed.path.endswith('-plan') else jobs.snapshot(key))
    if parsed.path in ('/api/panel/image-download','/api/panel/image-file'):
        from .image_download import service
        images=service(state.root);key=query.get('id',[''])[0]
        if parsed.path.endswith('/image-download'):return handler._json(200,images.load(key))
        path=images.file(key,query.get('kind',['original'])[0])
        handler.send_response(200);handler.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
        handler.send_header('Content-Length',str(path.stat().st_size));handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Referrer-Policy','no-referrer')
        if query.get('download')==['1']:handler.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
        handler.end_headers();handler.wfile.write(path.read_bytes());return
    if parsed.path=='/api/panel/config':
        from hinglish_captions.styles import SELECTABLE_TEMPLATES,template
        return handler._json(200,{'hosts':HOSTS,'tools':TOOLS,'caption_styles':[{'id':k,'name':template(k)['name']} for k in SELECTABLE_TEMPLATES],
                                  'choices':{'long':2,'short':5},'template_text':True,'capcut_native_panel':False})
    if parsed.path=='/api/panel/context':return handler._json(200,panel_service(state).contexts.load(query.get('id',[''])[0]))
    if parsed.path=='/api/panel/job':return handler._json(200,panel_service(state).snapshot(query.get('id',[''])[0]))
    if parsed.path=='/api/panel/broll-results':
        from .panel_broll_choices import saved_results
        return handler._json(200,{'results':saved_results(state.root)})
    if parsed.path=='/api/panel/broll-candidates':
        from .panel_broll_choices import cards
        context=panel_service(state).contexts.load(query.get('context_id',[''])[0])
        return handler._json(200,{'choices':cards(state.root,query.get('folder',[''])[0],context['content_format'])})
    if parsed.path=='/api/panel/visual-sources':
        from .visual_source_transport import VisualSourceTransport
        return handler._json(200,VisualSourceTransport(state).describe(query.get('job_id',[''])[0],query.get('project_path',[None])[0]))
    if parsed.path=='/api/panel/visual-results':
        from .completed_visual_jobs import results
        with state.lock:jobs=list(state.jobs.values())
        return handler._json(200,{'results':results(state.root,jobs)})
    if parsed.path=='/api/panel/sound-review':
        from .panel_sound_review import describe
        return handler._json(200,describe(state,query.get('job_id',[''])[0]))
    if parsed.path=='/api/panel/sound-results':
        from .panel_sound_review import saved_results
        with state.lock:jobs=list(state.jobs.values())
        return handler._json(200,{'results':saved_results(state,jobs)})
    if parsed.path=='/api/panel/sound-audition-media':
        from .panel_sound_review import preview
        descriptor=preview(state,query.get('job_id',[''])[0],query.get('audition_id',[''])[0])
        path=Path(descriptor['path']).resolve()
        if not path.is_relative_to((state.root/'output/sound-recommendations').resolve()) or descriptor['bytes']>7*1024**2:
            raise ValueError('Choose a prepared audition from this saved sound review.')
        data=path.read_bytes()
        if len(data)!=descriptor['bytes'] or hashlib.sha256(data).hexdigest()!=descriptor['sha256']:
            raise ValueError('This audition changed. Refresh the saved sound choice before listening.')
        handler.send_response(200);handler.send_header('Content-Type','audio/wav');handler.send_header('Content-Length',str(len(data)))
        handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Referrer-Policy','no-referrer')
        handler.end_headers();handler.wfile.write(data);return
    if parsed.path=='/api/panel/visual-source-media':
        from .visual_source_transport import VisualSourceTransport
        descriptor=VisualSourceTransport(state).resolve_media(query.get('job_id',[''])[0],query.get('project_path',[''])[0],
            query.get('manifest_sha256',[''])[0],query.get('asset_id',[''])[0])
        path=Path(descriptor['path']).resolve()
        if not path.is_relative_to((state.root/'output/visuals').resolve()) or descriptor['bytes']>40*1024**2:
            raise ValueError('Choose a supported source image from this saved visual review.')
        data=path.read_bytes()
        if len(data)!=descriptor['bytes'] or hashlib.sha256(data).hexdigest()!=descriptor['sha256']:
            raise ValueError('This image changed. Reopen the latest review before using it.')
        handler.send_response(200);handler.send_header('Content-Type',descriptor['mime'])
        handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store')
        handler.send_header('Referrer-Policy','no-referrer');handler.send_header('X-Content-Type-Options','nosniff')
        handler.end_headers();handler.wfile.write(data);return
    if not media:raise ValueError('Choose a supported editor-panel action.')
    path=Path(query.get('path',[''])[0]).resolve()
    if not path.is_relative_to((state.root/'output').resolve()) or not path.is_file() or path.suffix.lower() not in ('.mp4','.mov','.wav','.mp3','.png','.jpg','.jpeg','.webp'):
        raise ValueError('Choose a saved media option from this result.')
    handler.send_response(200);handler.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
    handler.send_header('Content-Length',str(path.stat().st_size));handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer');handler.end_headers()
    with path.open('rb') as source:
        while data:=source.read(256*1024):handler.wfile.write(data)


def post(handler,state,path,value):
    panels=panel_service(state)
    if path=='/api/panel/broll-website':
        from hinglish_broll.website_review import prepare_choice,start_saved_review,choose,continue_review
        action=value.get('action')
        if action=='start':return handler._json(202,start_saved_review(state.root,value.get('folder',''),value.get('orientation'),value.get('limit',6)))
        if action=='continue':return handler._json(202,continue_review(state.root,value.get('folder','')))
        if action=='choose':
            bank=choose(state.root,value.get('folder',''),value.get('slot_index'),value.get('source_id'))
            return handler._json(200,{'saved':True,'bank_id':bank['bank_id']})
        if value.get('host')!='aftereffects':raise ValueError('Use After Effects for this website review.')
        ensure_license(state,'aftereffects')
        from .broll_ae_direct import AfterEffectsDirect
        adapter=AfterEffectsDirect(state.root,panels.contexts)
        if action=='connect':
            context=adapter.capture()
            result={'name':context['name'],'context_id':context['id'],'transport':'aftereffects_script'}
        elif action=='select':
            from .timed_choice_delivery import TimedChoiceDelivery
            context=panels.contexts.load(value.get('context_id',''))
            if context.get('host')!='aftereffects' or context.get('transport')!='aftereffects_script':
                raise ValueError('Reconnect the intended After Effects composition.')
            manifest=prepare_choice(state.root,value.get('folder',''),value.get('slot_index'),value.get('source_id'),context)
            receipt=adapter.invoke_choice(manifest)
            accepted=TimedChoiceDelivery(state.root).accept(manifest['operation_id'],receipt,context=context)
            result={'id':manifest['operation_id'],'status':'confirmed','receipt':accepted,
                    'message':'After Effects confirmed your chosen video at the original speech timestamp.'}
        else:raise ValueError('Choose a website review action.')
        return handler._json(200,result)
    if path=='/api/panel/broll-native':
        from .broll_native_mailbox import service
        from .panel_broll_choices import report_request,select
        box=service(state);action=value.get('action')
        if action=='register':
            context=panels.contexts.load(value.get('context_id',''));ensure_license(state,context['host'])
            result=box.register(value.get('client'),context['id'])
        elif action in ('poll','receipt'):
            with box.lock:
                session=box._session(value.get('lease'),value.get('client'))
                ensure_license(state,session['context']['host'])
                result=({'command':box.poll(value.get('lease'),value.get('client'))} if action=='poll' else
                    box.ack(value.get('lease'),value.get('client'),value.get('id'),value.get('receipt'),error=value.get('error','')))
        elif action=='status':result=box.status(value.get('id'))
        elif action=='clear':
            form=value.get('content_format','short')
            if form not in ('short','long'):raise ValueError('Choose Short form or Long form.')
            request=report_request(state.root,{**value,'state':'no_broll'},form)
            result=select(state.root,request['folder'],request,{'content_format':form},'capcut')
        elif action in ('connect','select'):
            host=value.get('host');ensure_license(state,host)
            if host=='capcut':
                if action=='connect':result={'name':'New editable CapCut project','notice':'Opens a new project. Existing open clips are not swapped.'}
                else:
                    form=value.get('content_format','short')
                    if form not in ('short','long'):raise ValueError('Choose Short form or Long form.')
                    request=report_request(state.root,value,form)
                    request['defer_project']=value.get('defer_project') is True
                    result=select(state.root,request['folder'],request,{'host':'capcut','content_format':form},'capcut')
            elif host=='aftereffects' and action=='select' and value.get('transport')=='aftereffects_script':
                from .broll_ae_direct import AfterEffectsDirect
                context=panels.contexts.load(value.get('context_id',''))
                if context.get('host')!='aftereffects' or context.get('transport')!='aftereffects_script':
                    raise ValueError('Reconnect the actual After Effects composition before inserting B-roll.')
                request=report_request(state.root,value,context['content_format'])
                result=AfterEffectsDirect(state.root,panels.contexts).deliver(request['folder'],request,context['id'])
            else:
                with box.lock:
                    try:context=box.connection(host)['context']
                    except ValueError as error:
                        if host!='aftereffects' or action!='connect' or not str(error).startswith('Open Storylens in this editor'):raise
                        from .broll_ae_direct import AfterEffectsDirect
                        context=AfterEffectsDirect(state.root,panels.contexts).capture()
                        result={'name':context['name'],'context_id':context['id'],'transport':'aftereffects_script'}
                    else:
                        result=({'name':context.get('name',context['sequence_id'])} if action=='connect' else
                            box.submit(host,report_request(state.root,value,context['content_format'])))
        else:raise ValueError('Choose a supported B-roll editor connection action.')
        return handler._json(200,result)
    if path in ('/api/panel/template-text-start','/api/panel/template-text-stop','/api/panel/template-text-receipt'):
        from .template_text import service
        ensure_license(state,'aftereffects');jobs=service(state.root)
        if path.endswith('-start'):return handler._json(201,jobs.start(value))
        if path.endswith('-stop'):return handler._json(200,jobs.cancel(value.get('id','')))
        return handler._json(200,jobs.accept(value.get('id',''),value.get('receipt')))
    if path=='/api/panel/image-clipboard':
        from .image_download import service
        from .image_clipboard import read_image,read_html_address
        try:data=read_image()
        except ValueError:return handler._json(201,service(state.root).download(read_html_address()))
        return handler._json(201,service(state.root).ingest(data))
    if path=='/api/panel/image-clipboard-html':
        from .image_download import service
        from .image_clipboard import image_address
        html=value.get('html','')
        if not isinstance(html,str) or len(html)>500000:raise ValueError('Image download: copy one image first.')
        return handler._json(201,service(state.root).download(image_address(html)))
    if path in ('/api/panel/download-import','/api/panel/download-receipt'):
        from .panel_download_delivery import prepare,accept
        context=panels.contexts.load(value.get('context_id',''));ensure_license(state,context['host'])
        if path.endswith('/download-import'):return handler._json(200,prepare(state.root,value.get('id',''),value.get('kind',''),context))
        return handler._json(200,accept(state.root,value.get('id',''),value.get('kind',''),context,value.get('receipt')))
    if path in ('/api/panel/image-download','/api/panel/image-import','/api/panel/image-receipt'):
        from .image_download import service
        images=service(state.root)
        if path.endswith('/image-download'):return handler._json(201,images.download(value.get('url','')))
        context=panels.contexts.load(value.get('context_id',''))
        if context['host']!='aftereffects':raise ValueError('Image import: open the Storylens After Effects panel.')
        ensure_license(state,'aftereffects')
        if path.endswith('/image-import'):return handler._json(200,images.manifest(value.get('id',''),context['project_id']))
        return handler._json(200,images.accept(value.get('id',''),context['project_id'],value.get('receipt')))
    if path in ('/api/panel/photos','/api/panel/photo-receipt'):
        from hinglish_photos.service import service
        from hinglish_photos.editor_plugin import prepare,accept_receipt
        context=panels.contexts.load(value['context_id']) if value.get('context_id') else None
        host=context['host'] if context else value.get('host')
        ensure_license(state,host)
        if path.endswith('/photos'):
            photo_context={**context,'project_id':context.get('project_path',context['project_id'])} if context else None
            manifest=prepare(service(state.root),value.get('id',''),host,photo_context)
            if context:manifest['panel_project_id']=context['project_id']
            return handler._json(200,manifest)
        return handler._json(200,accept_receipt(service(state.root),value.get('id',''),host,value.get('receipt')))
    if path=='/api/panel/context':return handler._json(200,panels.contexts.save(value))
    if path=='/api/panel/run':return handler._json(202,panels.start(value))
    if path=='/api/panel/broll-choice':
        from .panel_broll_choices import select
        context=panels.contexts.load(value.get('context_id',''))
        ensure_license(state,context['host'])
        return handler._json(200,select(state.root,value.get('folder',''),value,context,context['host']))
    if path=='/api/panel/visual-source-choice':
        from .visual_source_transport import VisualSourceTransport
        context=panels.contexts.load(value.get('context_id',''))
        ensure_license(state,context['host'])
        importing=value.get('import_selected',False)
        if type(importing) is not bool:raise ValueError('Choose whether to import these selected images.')
        result=VisualSourceTransport(state).select(value.get('job_id',''),value)
        if importing:
            requested=value.get('choices',{})
            offered_ids={choice['asset_id'] for bank in result['banks']
                for choice in bank['choices'] if requested.get(str(bank['slot_index']))==choice['media_id']}
            paths=[r['path'] for r in result['selected_sources'] if r['asset_id'] in offered_ids]
            if not paths:raise ValueError('Choose an offered source image before importing it.')
            result['native_manifest']={'type':'assets','paths':list(dict.fromkeys(paths)),
                'name':'Storylens source images','insert':False,
                'expected':{k:context.get(k) for k in ('project_id','sequence_id')}}
        return handler._json(200,result)
    if path in ('/api/panel/sound-audition','/api/panel/sound-original'):
        from .panel_sound_review import audition,original
        context=panels.contexts.load(value.get('context_id',''));ensure_license(state,context['host'])
        args=(state,value.get('job_id',''),value.get('candidate_id',''))
        return handler._json(200,audition(*args) if path.endswith('sound-audition') else original(*args,context,insert=value.get('insert',False)))
    if path=='/api/panel/import':
        context=panels.contexts.load(value['context_id']) if value.get('context_id') else None
        host=context['host'] if context else value.get('host')
        ensure_license(state,host)
        return handler._json(200,prepare_import(state.root,host,value.get('folder',''),mode=value.get('mode',''),context=context,asset=value.get('asset')))
    if path=='/api/panel/capcut-context':
        ensure_license(state,'capcut')
        from .capcut_adapter import export_timeline
        xml=export_timeline(state.root,value.get('project_id'))
        return handler._json(200,panels.contexts.save({'host':'capcut','project_id':value['project_id'],'sequence_id':value['project_id'],
                                                     'timeline_xml':xml,'script':value.get('script',''),'content_format':value.get('content_format','short')}))
    raise ValueError('Choose an editor-panel action.')

def image_upload(handler,state):
    from .image_download import service
    length=int(handler.headers.get('Content-Length','0'))
    if not 0<length<=25*1024**2:raise ValueError('Image download: paste one image smaller than 25 MB.')
    return handler._json(201,service(state.root).ingest(handler.rfile.read(length)))
