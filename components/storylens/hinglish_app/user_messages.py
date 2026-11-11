"""Plain-language presentation; technical evidence remains in logs/details."""
import re
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('error_catalog.json').read_text('utf-8'))


def diagnostics(value):
    """Keep useful evidence without displaying connection secrets in Details."""
    text=str(value)
    text=re.sub(r'([?&](?:token|access_token|key|api_key)=)[^\s&#"\'<>]+',r'\1[hidden]',text,flags=re.I)
    text=re.sub(r'(Bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[hidden]',text,flags=re.I)
    text=re.sub(r'(["\']?(?:api_key|access_token|refresh_token|X-Hinglish-Token|X-Storylens-Browser)["\']?\s*[:=]\s*["\']?)[^\s,"\'}]+',r'\1[hidden]',text,flags=re.I)
    return text[:16000]


def editing_activity(line,previous='Preparing the video'):
    """Plain activity only; the caller retains the original technical log."""
    if re.search(r'\b(?:Error:|Traceback|engine stopped)',line,re.I):return line[:140]
    if re.search(r'\b(?:FutureWarning|DeprecationWarning|UserWarning)\b|warnings\.warn\(|Loading checkpoint shards:',line):
        return previous or 'Preparing the video'
    if re.search(r'Words and timing|Detecting speech|Understanding your speech|Transcribing',line,re.I):
        return 'Transcribing speech'
    return line[:140]


def problem(error, status=None, *, feature=None):
    text=str(error).strip()
    evidence=(type(error).__name__+': '+text) if isinstance(error,BaseException) else text
    stderr=getattr(error,'stderr',None)
    if stderr:evidence+='\n'+(stderr.decode('utf-8',errors='replace') if isinstance(stderr,bytes) else str(stderr))
    details=diagnostics(evidence)
    def result(code,message):
        if feature:message=feature+' stopped. '+message
        return {'code':code,'message':diagnostics(message),'details':details}
    for rule in catalog():
        if re.search(rule['pattern'],(feature+': ' if feature else '')+evidence,re.I):return result(rule['code'],rule['message'])
    if status==404:return result('not_found','This saved item or feature is unavailable. Refresh Storylens and select it again.')
    if status in (401,403):return result('connection_required','This page is not connected to Storylens. Reopen it from the local editor, then try again.')
    if status==413:return result('request_too_large','This request is too large to transfer. Add fewer files at a time, or shorten the text, then try again.')
    if isinstance(error,KeyError):return result('setting_missing','A required setting or saved item is missing. Refresh Storylens and select the files and settings again.')
    if isinstance(error,(TypeError,AttributeError,IndexError)):
        return result('invalid_settings','Storylens could not read the settings for this step. Reopen this feature and select its files and options again. If it still fails, keep the technical details for repair.')
    technical=bool(re.search(r'Traceback|\b(?:TypeError|KeyError|AttributeError|RuntimeError|IndexError|OSError|CalledProcessError)\b|^\(?[45]\d\d\b|https?://|^Command\s|exit (?:status|code)|\.py["\x27],? line|^\s*[\[{]',evidence,re.I))
    if technical or status and status>=500:
        return result('task_failed','Storylens could not finish this step because an unexpected error occurred. Check saved progress before retrying. If it happens again, keep the technical details for repair.')
    message=text or 'The request could not be completed. Check the selected files and settings, then try again.'
    if text and not re.search(r'\b(?:choose|select|check|try|reopen|refresh|start|resume|give|tell|supply|keep|connect|sign in|wait|attach|open|install|use|enter|paste|remove|split|name|enable|set)\b',text,re.I):
        message=text.rstrip('.')+'. Check this feature’s selected files and settings, then retry the unfinished step. For uploads, check saved receipts first.'
    return result('request_failed',message)


def failure(error, *, feature=None):
    issue=problem(error,feature=feature)
    return {'error':issue['message'],'error_code':issue['code'],'error_details':issue['details']}


def exception_status(error):
    if isinstance(error,FileNotFoundError):return 404
    if isinstance(error,PermissionError):return 403
    if isinstance(error,(ValueError,KeyError,TypeError)):return 400
    return 500


def extracted(count):
    return f'{count} Short'+('s' if count!=1 else '')+' extracted.'


def instagram_failure(review,error):
    posted=sum(row.get('status')=='published' for row in review.get('instagram_rows',[]))
    progress=f'{posted} Instagram video'+('s are' if posted!=1 else ' is')+' already posted. ' if posted else ''
    return 'Instagram could not finish this request. '+problem(error)['message'].rstrip('.')+'. '+progress+'Check the remaining videos’ saved status and times before retrying.'


def publication_result(review):
    parts=[]
    if review.get('youtube_check_only'):parts.append('YouTube checked; nothing uploaded.')
    elif review.get('ids'):
        count=review.get('scheduled_count',0)
        published=sum(bool(r.get('publication_verified')) for r in review.get('rows',[]))
        if published:parts.append(f'{published} YouTube video'+('s' if published!=1 else '')+' published and verified.')
        if count:parts.append(f'{count} YouTube video'+('s' if count!=1 else '')+' successfully scheduled.')
        elif not published and review.get('uploaded_count'):parts.append(f'{review["uploaded_count"]} video(s) uploaded to YouTube.')
    posted=[r for r in review.get('instagram_rows',[]) if r.get('status')=='published']
    if posted:
        earlier=[r for r in posted if r.get('previously_published')]
        new=[r for r in posted if not r.get('previously_published')]
        if new:
            handles=', '.join('@'+a for a in dict.fromkeys(r['account'] for r in new))
            parts.append(f'{len(new)} '+('new ' if earlier else '')+'video'+('s' if len(new)!=1 else '')+f' posted to Instagram ({handles}).')
        if earlier:
            if not new:parts.append('No new Instagram videos were uploaded in this request.')
            parts.append(f'{len(earlier)} video'+('s were' if len(earlier)!=1 else ' was')+' already posted earlier and not uploaded again.')
    return ' '.join(parts)
