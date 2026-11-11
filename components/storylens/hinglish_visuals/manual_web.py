"""Public image search -> file-validated sources for explicit HUMAN review.

No stock accounts, canonical-identity substitution, Vision, CLIP or auto placement.
Model-chosen speech slots/queries are data; this collector cannot execute code.
"""
import hashlib
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from hinglish_clean.detection import write_json
from .web import Media
from .websearch import WebSearch, MAX_IMAGE_BYTES
from .recovery import checkpoint


def _public_address(parsed):
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        return False
    host=parsed.hostname.casefold().rstrip('.')
    if host=='localhost' or host.endswith(('.localhost','.local')):return False
    try:return ipaddress.ip_address(host).is_global
    except ValueError:return True  # Existing public downloader owns DNS/redirect behavior.


def manual_choice(project, option):
    """Manual mode never promotes an existing negative visual verdict."""
    return (project.get('search_method') == 'website' and project.get('review_policy') == 'human'
            and isinstance(option, dict) and option.get('search_method') == 'website'
            and option.get('requires_human_review') is True
            and (option.get('evaluation') or {}).get('passed') is None
            and (option.get('file_validation') or {}).get('passed') is True)


def _queries(slot):
    values=list(slot.get('queries', []))+[slot.get('visual','')]
    if slot.get('show') == 'logo':
        values.insert(0, slot['label']+' logo png')
    return list(dict.fromkeys(q.strip() for q in values if isinstance(q,str) and q.strip()))[:3]


def _save(folder, project, stage, label='', *, selections=None):
    from .report import write_report
    checkpoint(folder, project, stage, label)
    if not project.get('collecting'):
        from .source_bank import build_source_bank
        from .source_result import _publish
        file=Path(folder)/'visuals-project.json'
        _publish(file,build_source_bank(file,selections))
    write_report(Path(folder)/'report.html', project)


def _adopt(folder, media, finder, slot):
    """Keep the source bytes; decoding is integrity checking, not visual approval."""
    url=urlparse(media.url)
    page=urlparse(media.page_url)
    if media.kind!='image' or not _public_address(url) or not _public_address(page):
        raise ValueError('This result needs a public source page and an image address.')
    stage=folder/'source-downloads'/(hashlib.sha256(media.url.encode()).hexdigest()+'.img')
    stage.parent.mkdir(parents=True,exist_ok=True)
    downloaded=Path(finder.download_image(media,stage))
    if downloaded.resolve()!=stage.resolve() or not downloaded.is_file():
        raise ValueError('The source download is not bound to this saved review.')
    if not 0<downloaded.stat().st_size<=MAX_IMAGE_BYTES:
        raise ValueError('The image file is empty or exceeds the supported size.')
    with Image.open(downloaded) as im:
        extension={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}.get(im.format)
        if extension is None or im.width*im.height>60_000_000:
            raise ValueError('Choose a supported PNG, JPEG or WebP source image.')
        size=list(im.size);im.verify()
    with Image.open(downloaded) as im:
        rgba=im.convert('RGBA')
        fingerprint=hashlib.sha256(rgba.resize((96,96)).tobytes()).hexdigest()
        thumb=folder/'thumbs'/(fingerprint[:24]+'.png')
        thumb.parent.mkdir(parents=True,exist_ok=True)
        rgba.thumbnail((480,480));rgba.save(thumb)
    raw=downloaded.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    target=folder/'references'/(digest+extension);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_bytes()!=raw:
        raise ValueError('A saved source changed. Keep the original review and retry with a new result.')
    if not target.exists():
        partial=target.with_suffix(target.suffix+'.partial');partial.write_bytes(raw);partial.replace(target)
    return {**media.to_dict(),'entity':slot['entity'],'asset':target.relative_to(folder).as_posix(),
        'path':str(target.resolve()),'report_thumb':thumb.relative_to(folder).as_posix(),
        'sha256':fingerprint,'file_sha256':digest,'search_method':'website','requires_human_review':True,
        'file_validation':{'passed':True,'dimensions':size,'bytes':len(raw),'sha256':digest},
        'evaluation':{'passed':None,'score':0.,'judge':'Human review required; Vision not run',
            'reasons':[],'warnings':['Identity, context and suitability have not been visually verified.'],
            'seen':'','checks':{'vision_checked':False}}}


def collect(root, results, finder, settings, progress=print, *, find_more=False, only_entity=None):
    """Checkpoint each query and accepted file; never call a visual/planning model."""
    from .pipeline import write_outputs
    if finder is None:
        raise ValueError('Website review needs public web image search. Enable web search and retry; saved work is kept.')
    target=getattr(settings,'options_per_moment',5)
    if type(target) is not int or target not in (2,5):
        raise ValueError('Choose two long-form or five short-form image options.')
    for timeline, folder, project in results:
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        if project.get('search_method')!='website' or project.get('review_policy')!='human':
            raise ValueError('Keep the verified review separate from this website-review project.')
        selections=None
        if (folder/'source-banks/active.json').is_file():
            from .source_result import _active
            _,prior=_active(folder/'visuals-project.json')
            selections={}
            for bank in prior['banks']:
                choice=bank['selection']
                selections[str(bank['slot_index'])]=(next(o['media_id'] for o in bank['choices']
                    if o['asset_id']==choice['asset_id']) if choice['state']=='selected' else
                    '' if choice['state']=='no_visual' else None)
        project.update(review_options=True,options_per_moment=target,collecting=True,vision_checked=False)
        _save(folder,project,'searching')
        try:
            for slot in project['slots']:
                if only_entity and slot['entity']!=only_entity:continue
                state=slot.setdefault('manual_research',{'completed_queries':[],'candidates':[],'failures':{}})
                if find_more:state['completed_queries']=[]
                options=slot.setdefault('options',[])
                fingerprints={o.get('sha256') for o in options}
                known={o.get('id') for o in options}
                attempted=set()
                if hasattr(finder,'begin_subject'):finder.begin_subject()
                queries=_queries(slot)
                for query in [None]+queries:
                    if len(options)>=target:break
                    if query is not None and query not in state['completed_queries']:
                        progress('Finding image options: '+slot['label'])
                        try:
                            found=finder.images(query,30,transparent=slot.get('show')=='logo') or []
                            ids={r['id'] for r in state['candidates']}
                            for media in found:
                                if isinstance(media,Media) and media.kind=='image' and media.id not in ids:
                                    state['candidates'].append(media.to_dict());ids.add(media.id)
                            state['completed_queries'].append(query)
                            _save(folder,project,'searching',slot['label'])
                        except Exception as error:
                            slot.setdefault('preparation_errors',[]).append(str(error))
                            progress('This source search could not finish. Other sources and saved choices are kept.')
                    for row in state['candidates'][:60]:
                        if len(options)>=target:break
                        if len(attempted)>=max(12,target*4):break
                        media_id=row.get('id')
                        if media_id in known or media_id in attempted or state['failures'].get(media_id,0)>=2:continue
                        attempted.add(media_id)
                        try:
                            media=Media(**{k:v for k,v in row.items() if k in Media.__dataclass_fields__})
                            option=_adopt(folder,media,finder,slot)
                            if option['sha256'] in fingerprints:continue
                            options.append(option);known.add(media.id);fingerprints.add(option['sha256'])
                            slot['alternatives']=list(options)
                            _save(folder,project,'downloading',slot['label'])
                            progress(f'{slot["label"]}: {len(options)}/{target} image options saved for your review')
                        except Exception as error:
                            state['failures'][media_id]=state['failures'].get(media_id,0)+1
                            slot.setdefault('preparation_errors',[]).append(str(error))
                        if len(attempted)>=max(12,target*4):break
                slot['shortfall']=max(0,target-len(options))
                _save(folder,project,'searching',slot['label'])
            project.pop('collecting',None)
            _save(folder,project,'ready' if all(len(s.get('options',[]))>=target for s in project['slots']) else 'partial',selections=selections)
            write_outputs(root,folder,project,progress,preview=False)
        except BaseException:
            project.pop('collecting',None)
            _save(folder,project,'paused',selections=selections)
            raise


def resume(root, project_file, progress=print, *, finder=None, find_more=False, only_entity=None):
    file=Path(project_file);project=json.loads(file.read_text('utf-8'))
    if project.get('search_method')!='website' or project.get('review_policy')!='human':
        raise ValueError('This is not a website-review project.')
    settings=type('ReviewSettings',(),{'options_per_moment':project.get('options_per_moment',5)})()
    collect(root,[(None,file.parent,project)],finder or WebSearch(root,progress),settings,progress,
            find_more=find_more,only_entity=only_entity)
    return {'filled':sum(len(s.get('options',[])) for s in project['slots']),
            'review_policy':'human','vision_checked':False}
