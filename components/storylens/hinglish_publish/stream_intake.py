"""One gaming recording -> one completed highlights edit -> Shorts from it."""
from contextlib import nullcontext
from pathlib import Path
import hashlib,json,time
from .store import fingerprint

def prepare_stream(publisher,payload,progress=print,work_lock=None):
    if payload.get('profile')!='gaming':raise ValueError('Choose Gaming for a stream-to-highlights edit.')
    root=Path(publisher.root);raw=str(payload.get('video_path','')).strip().strip(chr(34))
    request_key=hashlib.sha256(raw.encode()).hexdigest()
    folder=root/'cache/publisher/stream-intake'/request_key;folder.mkdir(parents=True,exist_ok=True)
    state_file=folder/'checkpoint.json'
    state=json.loads(state_file.read_text('utf-8')) if state_file.is_file() else {}
    def save(**values):
        state.update(values);temp=state_file.with_suffix('.partial');temp.write_text(json.dumps(state,indent=2),'utf-8');temp.replace(state_file)
    if raw.startswith(('http://','https://')):
        from hinglish_app.downloader import service,validate_request
        request=validate_request({'url':raw,'quality':'best','mode':'video'})
        if request['platform']!='youtube':raise ValueError('Use a finished YouTube stream link or a local recording.')
        downloads=service(root);job=None
        if state.get('download_id'):
            job=downloads.snapshot(state['download_id'])
            if job['request']['url']!=request['url']:raise ValueError('The saved stream download does not match this source.')
            if job['request'].get('quality') != 'best' and not state.get('highlight_project'):
                if job['status'] in ('queued','running','interrupted'):
                    raise ValueError('The earlier capped download is still pending. Cancel it in Downloader before requesting the highest-quality replay.')
                job=None
                save(download_id=None,source=None,source_sha256=None)
        if job is None or job['status'] in ('failed','cancelled'):
            job=downloads.start(request);save(download_id=job['id'])
        try:
            while job['status'] in ('queued','running'):
                progress('Downloading the stream: '+job.get('stage',''));time.sleep(.5);job=downloads.snapshot(job['id'])
        except Exception:
            downloads.cancel(job['id']);raise
        if job['status']!='complete':
            error=(job.get('error') or {}).get('message')
            raise ValueError(error or 'The stream download stopped. Check Downloader before retrying; saved files are kept.')
        source=downloads.media(job['id'],'video')
    else:
        source=Path(raw).resolve()
        if not source.is_file() or source.suffix.lower() not in ('.mp4','.mkv','.mov','.webm'):
            raise ValueError('Choose one finished local gaming recording or a YouTube stream link.')
    digest=fingerprint(source)
    if state.get('source_sha256') and state['source_sha256']!=digest:
        raise ValueError('This stream changed since preparation. Choose the updated recording as a new request; the previous edit is kept.')
    save(source=str(source),source_sha256=digest)
    from hinglish_niche.profiles import Profiles,use
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import preferred_device
    with (work_lock or nullcontext()),gpu_lock(root),use(Profiles(root).context('gaming')):
        highlight=None;project=None
        if state.get('highlight_project'):
            candidate=Path(state['highlight_project'])
            if not candidate.is_file():
                raise ValueError('The saved highlights project moved. Restore it before resuming its Shorts.')
            project=json.loads(candidate.read_text('utf-8'));highlight=Path(project['video'])
            if not highlight.is_file() or fingerprint(highlight)!=state.get('highlight_sha256'):
                raise ValueError('The saved highlights edit changed or moved. Restore that completed edit before resuming its Shorts.')
        if highlight is None:
            from hinglish_niche.gaming import run
            progress('Creating one highlights video from the stream')
            report=run(root,source,minutes=15,memes=True,device=preferred_device(root),progress=progress)
            projects=list(Path(report).parent.rglob('gaming-project.json'))
            if len(projects)!=1:raise ValueError('The gaming edit did not return exactly one completed highlights project.')
            project=json.loads(projects[0].read_text('utf-8'));highlight=Path(project['video']).resolve()
            if Path(project['source']).resolve()!=source.resolve() or not highlight.is_file():
                raise ValueError('The highlights output does not match the selected stream.')
            save(highlight_project=str(projects[0]),highlight_sha256=fingerprint(highlight))
        # Metadata uses the selected moments' actual spoken words. A full stream
        # script is never substituted for the trimmed highlights' content.
        transcript=' '.join(str(m.get('transcript','')) for m in project.get('moments',[])).strip()
        progress('Preparing the highlights and extracting Shorts from that finished edit')
        result=publisher.prepare_file({'video':str(highlight),'kind':'long','thumbnail':''},
            {**payload,'profile':'gaming','source_mode':'finished','video_path':str(highlight),'make_shorts':True,
             'shorts_source':str(highlight),'script':transcript},progress)
        save(stage='drafts_ready',job_ids=result['job_ids'])
        return {**result,'highlights_video':str(highlight),'source_video':str(source),'checkpoint':str(state_file)}
