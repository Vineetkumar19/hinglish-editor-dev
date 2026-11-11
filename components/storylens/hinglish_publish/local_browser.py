"""Local-only Chrome work queue. The model proposes bounded tasks, never browser code.

The extension has its own revocable key, not the editor's general control token.
Claimed uploads are never replayed after a disconnect or restart.
"""
import base64
import hashlib
import json
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

from .comment_window import publication_time
from .instagram_analytics_browser import ACTION as ANALYTICS_ACTION, receipt as analytics_receipt

HANDLE = re.compile(r'[A-Za-z0-9._]{1,30}')
TERMINAL = {'published', 'complete', 'blocked', 'needs_review', 'cancelled', 'submitted'}


def handle(value):
    value = str(value).strip().lstrip('@').lower()
    if not HANDLE.fullmatch(value):
        raise ValueError('Enter an exact Instagram username, without a link.')
    return value


def explicit_handles(text):
    """Parse @mentions in sentences without treating a final full stop as a name."""
    return [handle(value.rstrip('.')) for value in re.findall(r'(?<!\w)@([A-Za-z0-9._]+)',text)]


def resume_unsubmitted_weekly(job):
    """An interrupted pre-Save edit can wait again; uncertain Saves cannot."""
    if job['action']!='youtube_weekly_metadata' or job.get('submission_started') or job.get('stop'):
        return False
    job.update(status='queued',last_phase='queued',retry_at=time.time()+60,
        message='Waiting for Chrome, Studio and the connection to be ready again. No Save was submitted.')
    job.pop('lease',None)
    return True


COMMENT_ACTIONS = {'instagram_comments_read', 'instagram_comment_posts', 'instagram_comments_reply'}


class LocalBrowser:
    def __init__(self, root):
        self.folder = Path(root) / 'cache' / 'local-browser'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'state.json'
        self.lock = threading.RLock()
        self.seen = 0
        self.worker_version = ''
        self.worker_supports = []
        self._comment_authorizers = {}
        self.data = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {
            'key': secrets.token_urlsafe(32), 'accounts': {}, 'jobs': []}
        for job in self.data['jobs']:
            if job['status'] in ('running', 'sharing'):
                if resume_unsubmitted_weekly(job):continue
                message=('Chrome or Storylens restarted during a weekly YouTube edit. Check this exact video before approving another change.'
                    if job['action']=='youtube_weekly_metadata' else 'Chrome or the editor restarted. Check Instagram before trying again.')
                job.update(status='needs_review', message=message)
        self._save()

    def _save(self):
        from hinglish_app.durable_json import write
        # The comment inbox persists reply submission state separately from browser jobs.
        write(self.path, {**self.data,'jobs':[job for job in self.data['jobs']
            if job['action'] not in COMMENT_ACTIONS | {ANALYTICS_ACTION}]})

    def authorized(self, key):
        return bool(key) and secrets.compare_digest(str(key), self.data['key'])

    def pairing(self):
        return {'key': self.data['key'], 'extension_folder': str(Path(__file__).resolve().parents[1] / 'editor_plugins' / 'storylens-chrome')}

    def revoke(self):
        with self.lock:
            self.data['key'] = secrets.token_urlsafe(32)
            self.seen = 0
            for job in self.data['jobs']:
                if job['status'] not in TERMINAL:
                    job.update(status='needs_review', message='Chrome connection revoked. No automatic retry.')
            self._save()
        return self.snapshot()

    def bind(self, profile, username):
        if profile not in ('general', 'cricket', 'gaming'):
            raise ValueError('Choose General, Cricket or Gaming.')
        with self.lock:
            username=handle(username)
            for job in self.data['jobs']:
                if job['status']=='queued' and job.get('not_before') and (':'+profile+':') in job.get('reference','') and job['account']!=username:
                    job.update(status='needs_review',message='The saved destination account changed. Review the future Reel slots before posting.')
            self.data['accounts'][profile] = username
            self._save()
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return {'connected': time.time() - self.seen < 75, 'extension_version': self.worker_version,
                    'accounts': dict(self.data['accounts']),
                    'youtube_scheduling':time.time()-self.seen<75 and 'youtube_schedule' in self.worker_supports,
                    'youtube_publishing':time.time()-self.seen<75 and 'youtube_publish' in self.worker_supports,
                    'youtube_private_cleanup':time.time()-self.seen<75 and 'youtube_private' in self.worker_supports,
                    'youtube_weekly_metadata':time.time()-self.seen<75 and 'youtube_weekly_metadata' in self.worker_supports,
                    'jobs': [{k: v for k, v in j.items() if k not in ('video', 'lease', 'file_stamp', 'comments', 'comment_text', 'reply_text')}
                             for j in self.data['jobs'][-40:] if j['action'] != ANALYTICS_ACTION],
                    'readiness':self.readiness(),
                    'supports': ['account_check', 'reel_preview', 'reel_upload',*self.worker_supports], 'stories': 'Not verified in Instagram desktop; never silently posts a reel instead.'}

    def readiness(self):
        """Receipt-based health; connected/queued never means a post succeeded."""
        with self.lock:
            connected=time.time()-self.seen<75
            scheduled=[j for j in self.data['jobs'] if j['action']=='reel' and j.get('not_before')]
            waiting=[j for j in scheduled if j['status']=='queued']
            failures=[j for j in scheduled if j['status'] in ('needs_review','blocked')]
            return {'connected':connected,'queued':len(waiting),
                'published':sum(j['status']=='published' for j in scheduled),
                'attention_required':len(failures),
                'state':'attention_required' if failures else 'offline' if waiting and not connected else 'queued' if waiting else 'idle',
                'next_slot':min((j['publish_at'] for j in waiting),default=''),
                'failures':[{'id':j['id'],'account':j['account'],'publish_at':j.get('publish_at',''),
                    'message':j.get('message',''),'submission_started':bool(j.get('submission_started'))} for j in failures[-10:]],
                'rules':'Scheduled Instagram posts require Chrome and Storylens awake and online. '
                    'An account preflight is not proof that a Reel can upload. Only a verified permalink counts as published.'}

    def _preflight(self,job):
        """Read-only account check before a future slot; never uploads media."""
        check={'id':uuid.uuid4().hex[:16],'action':'inspect','account':job['account'],'video':'',
            'switch_via':job.get('switch_via',''),
            'caption':'','session':job.get('session',''),'status':'queued','created':time.time(),
            'message':'Account readiness check before the scheduled Instagram slot.',
            'file_stamp':None,'fingerprint':'preflight:'+job['id'],'stop':False,
            'submission_started':False,'last_phase':'queued','parent_id':job['id'],
            'not_before':max(time.time(),job['not_before']-300)}
        job['preflight_id']=check['id'];self.data['jobs'].append(check)

    def retry_account_readiness(self,job_id):
        """Recheck a timed-out identity before any Reel was submitted."""
        with self.lock:
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            check=next((j for j in self.data['jobs'] if j['id']==(job or {}).get('preflight_id')),None)
            allowed=('Instagram did not confirm the alternate account; no upload was started.',
                     'Instagram could not confirm the requested account after switching. No post was shared.')
            if (not job or job['action']!='reel' or job['status']!='needs_review'
                or job.get('submission_started') is not False or job.get('stop')
                or not check or check['action']!='inspect' or check['status']!='needs_review'
                or check.get('message') not in allowed or check['account']!=job['account']
                or not job.get('not_before')):
                raise ValueError('This account readiness failure cannot be retried automatically.')
            job.update(status='queued',lease='',message='Rechecking the scheduled account before uploading.')
            self._preflight(job)
            # A retry is an immediate read-only identity check even when the
            # original release is overdue. The parent keeps its original slot.
            self.data['jobs'][-1]['not_before']=time.time()
            self._save()
            return dict(job)

    def enqueue_youtube(self,channel_id,video_id,publish_at,session,*,authorized=False,preview=False,allow_reschedule=False,channel_name='',switch_via=None,video_kind='short',publish_now=False,metadata=None,expected_metadata=None,private_only=False):
        from datetime import datetime,timezone
        if not authorized or not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel_id) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id):
            raise ValueError('A reviewed YouTube channel and saved upload ID are required.')
        if type(allow_reschedule) is not bool:raise ValueError('Rescheduling requires an explicit boolean authorization.')
        if video_kind not in ('long','short'):raise ValueError('Choose a long video or Short.')
        if switch_via is not None:
            if not isinstance(switch_via,dict) or not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',switch_via.get('channel_id','')) or switch_via['channel_id']==channel_id or not switch_via.get('channel_name','').strip():
                raise ValueError('An exact alternate channel is required for a switch test.')
            switch_via={k:str(switch_via[k]).strip() for k in ('channel_id','channel_name')}
        if type(publish_now) is not bool or publish_now and (publish_at or preview):
            raise ValueError('Immediate publication needs an explicit choice without a future date or preview.')
        if type(private_only) is not bool or private_only and (publish_at or publish_now or preview or metadata is not None):
            raise ValueError('Private-only cleanup requires an exact saved video without a public release or copy change.')
        if metadata is not None:
            if publish_now or publish_at or preview or not isinstance(expected_metadata,dict):
                raise ValueError('Copy repair requires old and new copy without a visibility change.')
            for copy in (metadata,expected_metadata):
                if any(not isinstance(copy.get(k),str) or not copy[k].strip() or len(copy[k])>limit for k,limit in (('title',100),('description',5000))):
                    raise ValueError('Copy repair needs valid title and description.')
        elif not publish_now and not private_only:
            instant=datetime.fromisoformat(publish_at.replace('Z','+00:00'))
            if instant.tzinfo is None or instant.timestamp()<=time.time()+60:
                raise ValueError('Choose a future release time with an explicit time zone.')
            publish_at=instant.astimezone(timezone.utc).isoformat()
        action='youtube_private' if private_only else 'youtube_metadata' if metadata is not None else 'youtube_schedule_preview' if preview else 'youtube_schedule'
        identity=[action,channel_id,video_id,publish_at]
        if metadata is not None:identity.extend([metadata,expected_metadata])
        if allow_reschedule:identity.append('reschedule')
        digest=hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        with self.lock:
            existing=next((j for j in self.data['jobs'] if j.get('action')==action and j.get('fingerprint')==digest and j['status']!='cancelled'),None)
            if existing:
                if channel_name:existing['channel_name']=str(channel_name).strip()[:100]
                if switch_via:existing['switch_via']=switch_via
                existing['video_kind']=video_kind
                # A new authorized schedule request may retry a proven
                # pre-submission failure, reusing its exact ID and receipt.
                # Anything that crossed Schedule is verified separately.
                if existing['status'] in ('needs_review','blocked') and existing.get('submission_started') is False and not existing.get('stop'):
                    attempts=existing.setdefault('attempts',[])
                    attempts.append({k:existing.get(k) for k in ('status','message','finished','last_phase')})
                    existing.update(status='queued',lease='',last_phase='queued',
                        message='Retry requested before schedule submission; reusing the existing YouTube video.',updated=time.time())
                    self._save()
                return dict(existing)
            job={'id':uuid.uuid4().hex[:16],'action':action,'channel_id':channel_id,
                 'channel_name':str(channel_name).strip()[:100],
                 'switch_via':switch_via,
                 'video_kind':video_kind,
                 'video_id':video_id,'publish_at':publish_at,'session':session,'account':'','video':'',
                 'caption':'','status':'queued','created':time.time(),'message':'Waiting for YouTube Studio in Chrome.',
                 'fingerprint':digest,'stop':False,'submission_started':False,'last_phase':'queued',
                'allow_reschedule':allow_reschedule,'publish_now':publish_now,
                'needs_remote_confirmation':action=='youtube_schedule' and str(session).startswith('prepare-post:')}
            if metadata is not None:job.update(metadata=metadata,expected_metadata=expected_metadata)
            self.data['jobs'].append(job);self._save();return dict(job)

    def get(self, job_id):
        with self.lock:
            job = next((j for j in self.data['jobs'] if j['id'] == job_id), None)
            if not job:
                raise ValueError('Unknown Chrome task.')
            return dict(job)

    def retry_unapplied_youtube(self, job_id, private_receipt):
        """Bounded same-ID recovery after fresh independent private-only readback."""
        with self.lock:
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            proof=private_receipt or {};now=time.time()
            if (not job or job['action']!='youtube_schedule' or job.get('publish_now')
                    or job['status']!='submitted' or job.get('unapplied_retry_count',0)>=2
                    or now-job.get('submitted_at',now)<60
                    or proof.get('id')!=job['video_id'] or proof.get('privacy')!='private'
                    or proof.get('publish_at') or not 0<=now-proof.get('private_verified_at',0)<15):
                raise ValueError('Check this exact video’s current private-only receipt before retrying an unapplied schedule. No upload was repeated.')
            job.setdefault('attempts',[]).append({**{k:job.get(k) for k in
                ('status','message','submitted_at','finished','last_phase')},'private_only_readback':proof})
            job.update(status='queued',lease='',last_phase='queued',submission_started=False,
                unapplied_retry_count=job.get('unapplied_retry_count',0)+1,updated=now,needs_remote_confirmation=True,
                message='YouTube confirmed this existing video is still private with no schedule. Retrying the same release once.')
            job.pop('finished',None);job.pop('submitted_at',None)
            self._save();return dict(job)

    def confirm_youtube(self, job_id, remote):
        """Release the shared Studio tab only after independent platform readback."""
        from datetime import datetime
        with self.lock:
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            if not job or job['action']!='youtube_schedule' or job['video_id']!=remote.get('id'):
                raise ValueError('The YouTube confirmation does not match this saved task.')
            stamp=remote.get('publication_verified_at') if job.get('publish_now') else remote.get('schedule_verified_at')
            if not stamp or not 0<=time.time()-stamp<15:
                raise ValueError('A fresh independent YouTube confirmation is required.')
            if job.get('publish_now'):
                if remote.get('privacy')!='public':raise ValueError('YouTube has not confirmed public release.')
            elif (not remote.get('publish_at') or datetime.fromisoformat(remote['publish_at'].replace('Z','+00:00'))
                  !=datetime.fromisoformat(job['publish_at'].replace('Z','+00:00'))):
                raise ValueError('YouTube has not confirmed this exact release time.')
            job['remote_confirmed_at']=stamp;self._save();return dict(job)

    def saved_reel(self,reference,account,video):
        """Read an exact delivery even when it is older than the UI window."""
        with self.lock:
            matches=[j for j in self.data['jobs'] if j.get('action')=='reel' and j.get('reference')==reference
                and j.get('account')==account and j.get('video')==str(Path(video).resolve()) and j['status']!='cancelled']
            if len(matches)>1:raise ValueError('Multiple receipts match this Reel; verify them before changing its schedule.')
            return dict(matches[0]) if matches else None

    def verify_publication(self,job_id):
        """Read-only recovery of an uncertain Share; never replay the upload."""
        with self.lock:
            parent=self.get(job_id)
            if parent['action']!='reel' or parent['status']!='needs_review' or not parent.get('submission_started'):
                raise ValueError('Only an uncertain submitted Reel can request receipt verification.')
            existing=next((j for j in self.data['jobs'] if j['action']=='verify_reel'
                and j.get('verification_parent')==job_id and j['status'] in ('queued','running')),None)
            if existing:return dict(existing)
            job={'id':uuid.uuid4().hex[:16],'action':'verify_reel','account':parent['account'],
                'caption':parent['caption'],'video':'','file_stamp':None,'session':parent['session'],
                'status':'queued','created':time.time(),'reference':parent.get('reference',''),
                'verification_parent':job_id,'after':parent.get('submitted_at',parent['created'])-2,
                'before':parent.get('finished',time.time())+60,'stop':False,'submission_started':False,
                'last_phase':'queued','message':'Read-only receipt check queued; requires Local Publisher 0.4.8.'}
            self.data['jobs'].append(job);self._save();return dict(job)

    def inspect_account(self, profile=None):
        """Check a saved destination using the normal bounded Chrome adapter."""
        with self.lock:
            account=''
            if profile is not None:
                from hinglish_niche.profiles import valid_profile
                valid_profile(profile)
                account=self.data.get('accounts',{}).get(profile,'')
                if not account:raise ValueError('Choose this profile\'s saved Instagram account before checking it.')
            return self.enqueue('inspect',account)

    def enqueue(self, action, account='', video='', caption='', session='', *, authorized=False,publish_at='',reference='',switch_via=''):
        if action not in ('inspect', 'preview', 'reel', 'story'):
            raise ValueError('This Chrome action is unavailable.')
        if action == 'story':
            raise ValueError('Story uploads are not verified in Instagram desktop. No reel was posted instead.')
        account = handle(account) if account else ''
        if switch_via:
            switch_via=handle(switch_via)
            if not authorized or switch_via==account or switch_via not in self.data.get('accounts',{}).values():
                raise ValueError('A saved alternate Instagram account and explicit authorization are required for a switch test.')
        due=0
        if publish_at:
            from datetime import datetime
            instant=datetime.fromisoformat(publish_at.replace('Z','+00:00'))
            if action!='reel' or instant.tzinfo is None or instant.timestamp()<=time.time()+5:
                raise ValueError('Scheduled Reels require a future release time with a timezone.')
            due=instant.timestamp()
        stamp = None
        if action in ('reel', 'preview'):
            if not authorized or not account:
                raise ValueError('An upload request and an exact destination account are required.')
            p = Path(video).resolve()
            if not p.is_file() or p.suffix.lower() != '.mp4' or not 0 < p.stat().st_size <= 2 * 1024**3:
                raise ValueError('Choose a finished MP4 up to 2 GB.')
            if not isinstance(caption, str) or len(caption) > 2200:
                raise ValueError('Instagram caption must be text under 2,200 characters; it may be empty.')
            stat = p.stat()
            stamp = [stat.st_size, stat.st_mtime_ns]
            video = str(p)
        digest = hashlib.sha256(json.dumps([action, account, video, stamp, caption], ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            if action == 'reel':
                old = next((j for j in self.data['jobs'] if j.get('action') == 'reel' and j.get('fingerprint') == digest and j['status'] != 'cancelled'), None)
                if not old:
                    # Post text is editable metadata, not a new publication identity.
                    old=next((j for j in self.data['jobs'] if j.get('action')=='reel' and
                        j.get('account')==account and j.get('video')==video and
                        j.get('file_stamp')==stamp and j['status']!='cancelled'),None)
                    if old and old.get('caption')!=caption:
                        if (old['status'] not in ('queued','needs_review') or old.get('submission_started') is not False
                            or old.get('last_phase') not in ('queued','running') or old.get('stop')):
                            raise ValueError('This Reel already started or finished. Changing its text cannot create another upload; check its saved receipt.')
                        old.update(caption=caption,fingerprint=digest)
                        self._save()
                if old:
                    if old.get('publish_at','')!=publish_at:
                        safe_pause=old['status']=='needs_review' and old.get('submission_started') is False and old.get('last_phase') in ('queued','running')
                        if not publish_at and old['status'] not in ('queued',) and not safe_pause:
                            return dict(old)  # An immediate retry never duplicates an already started post.
                        if old['status']!='queued' and not safe_pause:raise ValueError('This Reel already started or finished. Check its saved receipt before changing its release.')
                        old.update(status='queued',stop=False,lease='',publish_at=publish_at,not_before=due,
                            message='Queued locally for '+publish_at+'. Keep Storylens and Chrome running.' if publish_at else 'Waiting for the local Chrome extension.')
                        check=next((j for j in self.data['jobs'] if j['id']==old.get('preflight_id')),None)
                        if check and check['status']=='queued':check.update(status='cancelled',message='The release date changed.')
                        old.pop('preflight_id',None)
                        if publish_at:self._preflight(old)
                        self._save()
                    elif old['status']=='needs_review' and old.get('submission_started') is False and old.get('last_phase') in ('queued','running') and not old.get('stop'):
                        return self.retry_before_share(old['id'])
                    return dict(old)
            job = {'id': uuid.uuid4().hex[:16], 'action': action, 'account': account, 'video': video,
                   'switch_via':switch_via,
                   'caption': caption, 'session': session, 'status': 'queued', 'created': time.time(),
                   'reference':str(reference)[:160],
                   'message': 'Waiting for the local Chrome extension.', 'file_stamp': stamp,
                   'fingerprint': digest, 'stop': False, 'submission_started': False, 'last_phase': 'queued'}
            if publish_at:job.update(publish_at=publish_at,not_before=due,reference=str(reference)[:160],message='Queued locally for '+publish_at+'. Keep Storylens and Chrome running.')
            self.data['jobs'].append(job)
            if publish_at:self._preflight(job)
            self._save()
            return dict(job)

    def expired_comment_posts(self, account, cutoff):
        from .instagram_comments import owned_post_id

        with self.lock:
            dates = self.data.get('comment_post_dates', {}).get(account, {})
            expired = {post_id for post_id, value in dates.items()
                       if (published := publication_time(value)) is not None and published <= cutoff}
            for job in self.data['jobs']:
                if job['action'] != 'reel' or job['status'] != 'published' or job['account'] != account:
                    continue
                confirmed_at = job.get('verification', {}).get('posted_at') or job.get('finished')
                url = job.get('url', '')
                if url.startswith(('https://www.instagram.com/reel/', 'https://www.instagram.com/p/')):
                    url = url.replace('https://www.instagram.com/', f'https://www.instagram.com/{account}/', 1)
                post_id = owned_post_id(account, url)
                # A verified publication receipt also gives an upper bound on its date.
                if post_id and isinstance(confirmed_at, (int, float)) and confirmed_at <= cutoff.timestamp():
                    expired.add(post_id)
            return expired

    def enqueue_comment_read(self, profile, account):
        return self.enqueue_comment_action(profile, account, 'instagram_comments_read')

    def enqueue_comment_action(self, profile, account, action, *, source_url=None,
                               comment_id=None, author=None, comment_text=None,
                               reply_text=None, authorize=None, cutoff=None):
        from .instagram_comments import ACCOUNTS, COMMENT_ID, HANDLE, POST_PATH
        from urllib.parse import urlsplit
        with self.lock:
            if ACCOUNTS.get(profile) != account or self.data['accounts'].get(profile) != account:
                raise ValueError('The exact saved Instagram destination changed.')
            if action not in COMMENT_ACTIONS:
                raise ValueError('Choose an Instagram comment operation.')
            capability = 'instagram_comments_read' if action == 'instagram_comments_read' and not source_url else 'instagram_comments_window'
            if time.time() - self.seen >= 75 or capability not in self.worker_supports:
                raise ValueError('Connect the updated Storylens Chrome extension for this comment task.')
            if source_url:
                url = urlsplit(source_url)
                post = POST_PATH.fullmatch(url.path)
                if (url.scheme != 'https' or url.netloc != 'www.instagram.com' or
                        url.query or url.fragment or not post or post['owner'] != account):
                    raise ValueError('The Instagram post must belong to the exact saved account.')
            if action == 'instagram_comments_reply' and (
                    not source_url or not callable(authorize) or not COMMENT_ID.fullmatch(comment_id or '')
                    or not HANDLE.fullmatch(author or '') or author.casefold() == account
                    or not isinstance(comment_text, str) or not 1 <= len(comment_text) <= 2200
                    or not isinstance(reply_text, str) or not 1 <= len(reply_text.strip()) <= 350):
                raise ValueError('The exact Instagram comment and reply are required.')
            job = {'id': uuid.uuid4().hex[:16], 'action': action, 'profile': profile,
                   'account': account, 'video': '', 'caption': '', 'status': 'queued',
                   'stop': False, 'submission_started': False, 'created': time.time(),
                   'message': 'Waiting for the signed-in Chrome extension.'}
            if source_url:
                job['source_url'] = source_url
            if action == 'instagram_comments_read' and source_url:
                if publication_time(cutoff) is None:
                    raise ValueError('The Instagram post scan requires a publication cutoff.')
                job['cutoff'] = cutoff
            if action == 'instagram_comments_reply':
                job.update(comment_id=comment_id, author=author, comment_text=comment_text, reply_text=reply_text)
                self._comment_authorizers[job['id']] = authorize
            self.data['jobs'].append(job)
            return job['id']

    def discard_comment_read(self, job_id):
        with self.lock:
            job = next((item for item in self.data['jobs'] if item['id'] == job_id
                        and item['action'] in COMMENT_ACTIONS), None)
            if job:
                self.data['jobs'].remove(job)
            self._comment_authorizers.pop(job_id, None)
            return dict(job) if job else None

    def instagram_analytics_ready(self):
        with self.lock:
            return time.time() - self.seen < 75 and ANALYTICS_ACTION in self.worker_supports

    def enqueue_instagram_analytics(self, profile, account):
        from .instagram_comments import ACCOUNTS
        with self.lock:
            if ACCOUNTS.get(profile) != account or self.data['accounts'].get(profile) != account:
                raise ValueError('Connect the exact Instagram account in the existing StoryLens Chrome connection.')
            if not self.instagram_analytics_ready():
                raise ValueError('Open the paired Chrome profile and reload the existing StoryLens Local Publisher extension for Analytics.')
            job_id = uuid.uuid4().hex[:16]
            self.data['jobs'].append({'id': job_id, 'action': ANALYTICS_ACTION, 'profile': profile, 'account': account,
                'status': 'queued', 'caption': '', 'video': '', 'created': time.time(), 'stop': False,
                'submission_started': False, 'message': 'Waiting for the paired Chrome browser.'})
            return job_id

    def finish_instagram_analytics_wait(self, job_id):
        with self.lock:
            self.data['jobs'][:] = [job for job in self.data['jobs']
                                   if not (job['id'] == job_id and job['action'] == ANALYTICS_ACTION)]

    def claim(self, version='', supports=()):
        with self.lock:
            self.seen = time.time()
            self.worker_version = str(version)[:20]
            self.worker_supports=[]
            if version in ('0.4.0','0.4.1','0.4.2','0.4.3','0.4.4','0.4.5','0.4.6','0.4.7','0.4.8','0.4.9','0.4.10','0.4.11','0.4.12','0.4.13','0.4.14','0.4.15','0.4.16','0.4.17','0.4.18','0.4.19','0.4.20','0.4.21','0.4.22','0.4.23','0.4.24','0.4.25','0.4.26','0.4.27','0.4.28','0.4.29','0.4.30','0.4.31','0.4.32','0.4.33','0.4.34','0.4.35','0.4.36','0.4.37','0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44') and isinstance(supports,list):
                self.worker_supports=[s for s in ('youtube_schedule','youtube_preview','youtube_publish','youtube_metadata','youtube_private') if s in supports and (s!='youtube_preview' or version in ('0.4.4','0.4.5','0.4.6','0.4.7','0.4.8','0.4.9','0.4.10','0.4.11','0.4.12','0.4.13','0.4.14','0.4.15','0.4.16','0.4.17','0.4.18','0.4.19','0.4.20','0.4.21','0.4.22','0.4.23','0.4.24','0.4.25','0.4.26','0.4.27','0.4.28','0.4.29','0.4.30','0.4.31','0.4.32','0.4.33','0.4.34','0.4.35','0.4.36','0.4.37','0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44'))]
            if version in ('0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44') and isinstance(supports,list) and 'youtube_weekly_metadata' in supports:
                self.worker_supports.append('youtube_weekly_metadata')
            if version in ('0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44') and isinstance(supports,list) and 'instagram_comments_read' in supports:
                self.worker_supports.append('instagram_comments_read')
            if version in ('0.4.41','0.4.42','0.4.43','0.4.44') and isinstance(supports, list) and 'instagram_comments_reply' in supports:
                self.worker_supports.append('instagram_comments_reply')
            if version in ('0.4.43','0.4.44') and isinstance(supports, list) and {
                    'instagram_comments_read', 'instagram_comments_reply', 'instagram_comments_window'}.issubset(supports):
                self.worker_supports.append('instagram_comments_window')
            if version == '0.4.44' and isinstance(supports, list) and ANALYTICS_ACTION in supports:
                self.worker_supports.append(ANALYTICS_ACTION)
            from .weekly_seo import sync as sync_weekly
            try:sync_weekly(self)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Weekly SEO plan check failed; existing browser tasks remain available')
            # An authorized, unstarted Reel stays due after sleep/offline time.
            # Keep its original slot and identity; never revive an uncertain Share.
            for old in self.data['jobs']:
                timeout=90 if old['action']=='youtube_weekly_metadata' and not old.get('submission_started') else 1200
                if old['status'] in ('running', 'sharing') and time.time() - old.get('updated', old['created']) > timeout:
                    if resume_unsubmitted_weekly(old):self._save();continue
                    message=('Chrome disconnected during a weekly YouTube edit. Check this exact video; future weeks are paused.'
                        if old['action']=='youtube_weekly_metadata' else 'Chrome disconnected. Check Instagram before trying again.')
                    old.update(status='needs_review', message=message)
                    self._save()
            if any(j['status'] in ('running', 'sharing') for j in self.data['jobs']):
                return {'job': None}
            def eligible(j):
                if j['status']!='queued':return False
                if j['action'] == ANALYTICS_ACTION:
                    return ANALYTICS_ACTION in self.worker_supports and self.data['accounts'].get(j['profile']) == j['account']
                if j['action'] in COMMENT_ACTIONS:
                    capability = ('instagram_comments_read'
                                  if j['action'] == 'instagram_comments_read' and not j.get('source_url')
                                  else 'instagram_comments_window')
                    return capability in self.worker_supports and self.data['accounts'].get(j['profile']) == j['account']
                if j['action']=='youtube_weekly_metadata':
                    if 'youtube_weekly_metadata' not in self.worker_supports:return False
                    from .weekly_seo_browser import eligible as weekly_eligible
                    if not weekly_eligible(self,j,time.time()):return False
                if j['action'].startswith('youtube_') and any(
                        other.get('needs_remote_confirmation') and other['status']=='submitted'
                        and not other.get('remote_confirmed_at')
                        and time.time()-other.get('updated',other['created'])<90
                        for other in self.data['jobs']):
                    return False
                if j['action']=='youtube_metadata' and 'youtube_metadata' not in self.worker_supports:return False
                if j['action']=='youtube_private' and 'youtube_private' not in self.worker_supports:return False
                if j.get('publish_now') and 'youtube_publish' not in self.worker_supports:return False
                if j.get('switch_via'):
                    try:
                        if tuple(map(int,version.split('.')))<(0,4,29):return False
                    except (TypeError,ValueError):return False
                if j['action']=='verify_reel' and version not in ('0.4.8','0.4.9','0.4.10','0.4.11','0.4.12','0.4.13','0.4.14','0.4.15','0.4.16','0.4.17','0.4.18','0.4.19','0.4.20','0.4.21','0.4.22','0.4.23','0.4.24','0.4.25','0.4.26','0.4.27','0.4.28','0.4.29','0.4.30','0.4.31','0.4.32','0.4.33','0.4.34','0.4.35','0.4.36','0.4.37','0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44'):return False
                if j.get('preflight_id'):
                    check=next((p for p in self.data['jobs'] if p['id']==j['preflight_id']),None)
                    if not check or check['status']!='complete':
                        if not check or check['status'] in TERMINAL:
                            j.update(status='needs_review',message='The scheduled account readiness check failed. '+(check.get('message','') if check else 'The check is missing.'))
                            self._save()
                        return False
                if max(j.get('not_before',0),j.get('retry_at',0))>time.time():return False
                if j.get('parent_id'):
                    parent=next((p for p in self.data['jobs'] if p['id']==j['parent_id']),None)
                    if not parent or parent['status']!='queued':
                        j.update(status='cancelled',message='The parent schedule is no longer queued.');self._save();return False
                if j['action'].startswith('youtube_schedule') and j.get('allow_reschedule') is True and self.worker_version not in ('0.4.7','0.4.8','0.4.9','0.4.10','0.4.11','0.4.12','0.4.13','0.4.14','0.4.15','0.4.16','0.4.17','0.4.18','0.4.19','0.4.20','0.4.21','0.4.22','0.4.23','0.4.24','0.4.25','0.4.26','0.4.27','0.4.28','0.4.29','0.4.30','0.4.31','0.4.32','0.4.33','0.4.34','0.4.35','0.4.36','0.4.37','0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44'):return False
                if j['action']=='youtube_schedule_preview':return 'youtube_preview' in self.worker_supports
                return j['action']!='youtube_schedule' or 'youtube_schedule' in self.worker_supports
            parents={j['id']:j for j in self.data['jobs']}
            def release_order(j):
                owner=parents.get(j.get('parent_id')) or j
                return owner.get('not_before',owner['created'])
            job = min((j for j in self.data['jobs'] if eligible(j)),key=release_order,default=None)
            if not job:
                return {'job': None}
            if job['action'] == 'preview' and self.worker_version not in ('0.1.1', '0.1.2', '0.1.3', '0.2.0', '0.2.1', '0.2.2', '0.2.3', '0.3.0','0.4.0','0.4.1','0.4.2','0.4.3','0.4.4','0.4.5','0.4.6','0.4.7','0.4.8','0.4.9','0.4.10','0.4.11','0.4.12','0.4.13','0.4.14','0.4.15','0.4.16','0.4.17','0.4.18','0.4.19','0.4.20','0.4.21','0.4.22','0.4.23','0.4.24','0.4.25','0.4.26','0.4.27','0.4.28','0.4.29','0.4.30','0.4.31','0.4.32','0.4.33','0.4.34','0.4.35','0.4.36','0.4.37','0.4.38','0.4.39','0.4.40','0.4.41','0.4.42','0.4.43','0.4.44'):
                return {'job': None, 'message': 'Reload Storylens Local Publisher in Chrome to enable preview mode.'}
            job.update(status='running', updated=time.time(), lease=secrets.token_urlsafe(24), message='Chrome is checking YouTube Studio.' if job['action'].startswith('youtube_') else 'Chrome is checking Instagram.')
            self._save()
            keys=('id','action','channel_id','video_id','publish_at','lease') if job['action'].startswith('youtube_') else ('id', 'action', 'account', 'caption', 'lease')
            payload={k:job[k] for k in keys}
            if job['action'] in COMMENT_ACTIONS:
                payload.update({key: job[key] for key in
                    ('source_url', 'cutoff', 'comment_id', 'author', 'comment_text', 'reply_text') if key in job})
            if not job['action'].startswith('youtube_'):
                workflow_path=self.folder.parents[1]/'config.workflow.local.json'
                workflow=json.loads(workflow_path.read_text('utf-8')) if workflow_path.exists() else {}
                payload['switch_labels']={target['instagram']:target.get('instagram_switch_labels',[])
                    for target in workflow.get('destinations',{}).values() if target.get('instagram') in self.data['accounts'].values()}
            if job.get('switch_via'):payload['switch_via']=job['switch_via']
            if job['action']=='verify_reel':
                payload.update(after=job['after'],before=job['before'])
            if job['action'].startswith('youtube_'):
                payload['allow_reschedule']=job.get('allow_reschedule') is True
                payload['channel_name']=job.get('channel_name','')
                payload['video_kind']=job.get('video_kind','short')
                payload['publish_now']=job.get('publish_now') is True
                payload['recover_before_submit']=bool(job.get('attempts') and not job.get('submission_started'))
                if job['action']=='youtube_metadata':payload.update(metadata=job['metadata'],expected_metadata=job['expected_metadata'])
                if job['action']=='youtube_weekly_metadata':
                    payload.update(metadata=job['metadata'],expected_metadata=job['expected_metadata'],
                        thumbnail=job.get('thumbnail'),week=job['week'],plan_id=job['plan_id'])
            return {'job': payload,
                    'media': {'name': Path(job['video']).name, 'size': job['file_stamp'][0], 'path': job['video']} if job['video'] else None}

    def _leased(self, job_id, lease):
        job = next((j for j in self.data['jobs'] if j['id'] == job_id), None)
        if not job or not secrets.compare_digest(str(lease), job.get('lease', '')) or not lease:
            raise ValueError('This Chrome task is not claimed by this extension.')
        return job

    def phase(self, job_id, lease, status, message=''):
        with self.lock:
            job = self._leased(job_id, lease)
            self.seen = time.time()
            if job['status'] in TERMINAL:
                return {'stop': True}
            if status not in ('running', 'sharing') or (job['status'] == 'sharing' and status != 'sharing'):
                raise ValueError('Invalid Chrome task phase.')
            if job['action']=='youtube_schedule_preview' and status=='sharing':
                raise ValueError('A Studio preview cannot submit a schedule.')
            if job['action'] in {'instagram_comments_read', 'instagram_comment_posts'} and status=='sharing':
                raise ValueError('An Instagram comment read cannot submit a reply.')
            if job['action'] == ANALYTICS_ACTION and status == 'sharing':
                raise ValueError('Analytics tasks cannot submit content.')
            if job['action']=='verify_reel' and status=='sharing':
                raise ValueError('A receipt check cannot publish.')
            if job['stop']:
                return {'stop': True}
            if job['action'] == 'instagram_comments_reply' and status == 'sharing':
                authorize = self._comment_authorizers.pop(job_id, None)
                if (not authorize or job['submission_started'] or
                        self.data['accounts'].get(job['profile']) != job['account']):
                    return {'stop': True}
                try:
                    authorize()
                except (ValueError, RuntimeError):
                    job.update(stop=True, message='Instagram reply authorization changed before submission.')
                    return {'stop': True}
            if job['action']=='youtube_weekly_metadata':
                from .weekly_seo import Plans,current_channel
                plan=Plans(self.folder.parents[1]).get(job['plan_id'])
                if not plan.get('enabled') or plan.get('status')=='needs_review' or current_channel(self.folder.parents[1],plan['profile'])!=job['channel_id']:
                    job.update(stop=True,message='Weekly authorization or channel changed. No further Studio actions are allowed.');self._save();return {'stop':True}
                if job.get('thumbnail'):
                    from .prepare_post import verify_identity
                    verify_identity(job['thumbnail'])
            if job['video'] and status == 'running':
                stat = Path(job['video']).stat()
                if [stat.st_size, stat.st_mtime_ns] != job['file_stamp']:
                    raise ValueError('The selected video changed. Prepare the updated export again.')
            job.update(status=status, last_phase=status, updated=time.time(), message=str(message)[:300])
            if status == 'sharing':
                job['submission_started'] = True
                job.setdefault('submitted_at',time.time())
            self._save()
            return {'stop': False}

    def media(self, job_id, lease, offset):
        with self.lock:
            job = self._leased(job_id, lease)
            if job['action'].startswith('youtube_schedule'):
                raise ValueError('Scheduling tasks cannot read local media.')
            if job['status'] != 'running' or job['stop'] or type(offset) is not int or offset < 0:
                raise ValueError('This task cannot read upload media.')
            p = Path(job['video'])
            stat = p.stat()
            if [stat.st_size, stat.st_mtime_ns] != job['file_stamp'] or offset >= stat.st_size:
                raise ValueError('The upload video changed or the media offset is invalid.')
            with p.open('rb') as stream:
                stream.seek(offset)
                data = stream.read(1024 * 1024)
            self.seen = time.time()
            return {'offset': offset, 'bytes': len(data), 'data': base64.b64encode(data).decode('ascii')}

    def finish(self, job_id, lease, result):
        with self.lock:
            job = self._leased(job_id, lease)
            if job['status'] in TERMINAL:
                return self.get(job_id)
            status = result.get('status')
            if job['action']=='youtube_weekly_metadata':
                from .weekly_seo_browser import finish as finish_weekly
                return finish_weekly(self,job,result)
            if status not in TERMINAL:
                raise ValueError('Invalid Chrome result.')
            if job['action'] == ANALYTICS_ACTION:
                if status not in ('complete', 'needs_review', 'blocked', 'cancelled'):
                    raise ValueError('Analytics tasks cannot submit content.')
                if status == 'complete':
                    job['analytics'] = analytics_receipt(job, result, self.data['accounts'])
                job.update(status=status, message=str(result.get('message', ''))[:260], finished=time.time())
                return self.get(job_id)
            if result.get('switch_trace'):
                trace=result['switch_trace']
                if not isinstance(trace,list) or not 1<=len(trace)<=5 or not all(isinstance(v,str) for v in trace):raise ValueError('Invalid account-switch evidence.')
                target=job.get('channel_id') if job['action'].startswith('youtube_') else job.get('account')
                # A general account inspection observes the signed-in account;
                # it does not request a switch or change any saved binding.
                if job['action']=='inspect' and not target and status=='complete':
                    target=handle(result.get('account',''))
                    if not target:raise ValueError('Account inspection needs an observed Instagram account.')
                via=job.get('switch_via');via=via.get('channel_id') if isinstance(via,dict) else via
                if trace[-1]!=target or via and trace[0]==target and via not in trace:raise ValueError('Account-switch evidence does not match the requested round trip.')
                job['switch_trace']=trace
            if job['action'] in COMMENT_ACTIONS:
                from .instagram_comments import COMMENT_ID, POST_PATH, owned_post_id, validate_rows
                from urllib.parse import urlsplit
                if status not in ('complete', 'needs_review', 'blocked', 'cancelled'):
                    raise ValueError('An Instagram comment task cannot submit a post.')
                if status == 'complete':
                    if (job.get('stop') or result.get('account') != job['account'] or
                            self.data['accounts'].get(job['profile']) != job['account']):
                        raise ValueError('Instagram account changed during the comment task.')
                    if job['action'] == 'instagram_comment_posts':
                        posts = result.get('posts')
                        if not isinstance(posts, list) or len(posts) > 1000:
                            raise ValueError('Chrome returned an invalid Instagram post list.')
                        for source in posts:
                            parsed = urlsplit(source)
                            post = POST_PATH.fullmatch(parsed.path)
                            if (parsed.scheme != 'https' or parsed.netloc != 'www.instagram.com' or
                                    not post or post['owner'] != job['account'] or parsed.query or parsed.fragment):
                                raise ValueError('Chrome returned a post outside the saved Instagram account.')
                        job['posts'] = list(dict.fromkeys(posts))
                    elif job['action'] == 'instagram_comments_reply':
                        receipt_id = result.get('reply_id')
                        if (not job['submission_started'] or
                                not isinstance(receipt_id, str) or not COMMENT_ID.fullmatch(receipt_id) or
                                result.get('parent_id') != job['comment_id'] or
                                result.get('source_url') != job['source_url'] or result.get('text') != job['reply_text']):
                            raise ValueError('Chrome did not confirm the exact Instagram reply.')
                        job['reply_id'] = receipt_id
                    else:
                        rows = result.get('rows')
                        empty_source = result.get('empty_source')
                        if job.get('source_url'):
                            account = job['account']
                            expected_id = owned_post_id(account, job['source_url'])
                            source_id = owned_post_id(account, result.get('source_url'))
                            published = publication_time(result.get('source_published_at'))
                            if (source_id != expected_id or published is None or published.timestamp() > time.time()):
                                raise ValueError('Chrome did not verify the exact Instagram publication date.')
                            expired = published <= publication_time(job['cutoff'])
                            if expired:
                                if rows != [] or result.get('expired_source') is not True:
                                    raise ValueError('Chrome returned comments for an expired Instagram post.')
                                comments = []
                            else:
                                comments = validate_rows(account, rows, empty_source=empty_source)
                                if (any(row['source_id'] != source_id for row in comments)
                                        or not comments and owned_post_id(account, empty_source) != source_id):
                                    raise ValueError('Chrome read comments from a different Instagram post.')
                            stamp = published.isoformat(timespec='microseconds')
                            for row in comments:
                                row['source_published_at'] = stamp
                            dates = self.data.setdefault('comment_post_dates', {}).setdefault(account, {})
                            if dates.get(source_id) != stamp:
                                dates[source_id] = stamp
                                self._save()
                            job.update(comments=comments, source_published_at=stamp, expired_source=expired)
                        else:
                            job['comments'] = validate_rows(job['account'], rows, empty_source=empty_source)
                job.update(status=status, message=str(result.get('message', ''))[:500], finished=time.time())
                return self.get(job_id)
            if job['action']=='verify_reel':
                if status not in ('complete','needs_review','blocked','cancelled'):
                    raise ValueError('A receipt check cannot submit or publish.')
                if status=='complete':
                    parent=next(j for j in self.data['jobs'] if j['id']==job['verification_parent'])
                    account=handle(result.get('account',''));url=str(result.get('url',''))
                    posted=result.get('posted_at')
                    match=re.fullmatch(r'https://www\.instagram\.com/([A-Za-z0-9._]+)/(?:reel|p)/[A-Za-z0-9_-]+/',url)
                    if (parent['status']!='needs_review' or not parent.get('submission_started')
                        or account!=parent['account'] or not match or match[1].lower()!=account
                        or result.get('caption_verified') is not True or type(posted) not in (int,float)
                        or not job['after']<=posted<=job['before']):
                        raise ValueError('Existing publication lacks matching account, caption and time evidence.')
                    parent.update(status='published',url=url,finished=time.time(),
                        message='Existing Instagram publication verified by the local extension; no upload repeated.',
                        verification={'job_id':job['id'],'posted_at':posted,'method':'extension_existing_post'})
                job.update(status=status,message=str(result.get('message',''))[:500],finished=time.time())
                self._save();return self.get(job_id)
            if job['action']=='youtube_schedule_preview':
                if status not in ('complete','needs_review','blocked','cancelled'):
                    raise ValueError('A Studio preview cannot submit a schedule.')
                if status=='complete' and (job.get('submission_started') or result.get('controls_verified') is not True or result.get('driver_version') not in ('0.4.4','0.4.5','0.4.6','0.4.7') or
                        any(result.get(k)!=job[k] for k in ('video_id','channel_id','publish_at'))):
                    raise ValueError('Preview requires matching date, channel, video and control evidence.')
                job.update(status=status,message=str(result.get('message',''))[:500],finished=time.time(),
                           controls_verified=status=='complete',driver_version=result.get('driver_version',''))
                self._save();return self.get(job_id)
            if job['action'] in ('youtube_schedule','youtube_metadata','youtube_private'):
                if status not in ('submitted','needs_review','blocked','cancelled'):
                    raise ValueError('Chrome cannot assert that a YouTube schedule is verified.')
                if status=='submitted' and (job['status']!='sharing' or
                    any(result.get(k)!=job[k] for k in ('video_id','channel_id','publish_at'))):
                    raise ValueError('Schedule submission lacks matching reviewed video evidence.')
                if status=='submitted' and job['action']=='youtube_private' and result.get('private_only') is not True:
                    raise ValueError('Private cleanup lacks its exact private-only submission evidence.')
                job.update(status=status,message=str(result.get('message',''))[:500],finished=time.time())
                self._save();return self.get(job_id)
            if status=='submitted':raise ValueError('Only YouTube Studio tasks can submit a schedule.')
            account = handle(result['account']) if result.get('account') else ''
            url = str(result.get('url', ''))
            if status=='complete' and job.get('parent_id') and account!=job['account']:
                raise ValueError('The readiness check must verify the exact scheduled account.')
            safe_reset='[storylens-safe-retry:empty-composer]' in str(result.get('message',''))
            if (status=='needs_review' and safe_reset and job['action'] in ('reel','preview') and
                job.get('submission_started') is False and not job.get('stop') and
                job.get('last_phase')=='running' and job.get('retry_count',0)<2):
                p=Path(job['video']);stat=p.stat()
                if [stat.st_size,stat.st_mtime_ns]==job['file_stamp']:
                    job.setdefault('attempts',[]).append({'finished':time.time(),'message':str(result.get('message',''))[:500]})
                    job.update(status='queued',lease='',retry_at=time.time()+5,retry_count=job.get('retry_count',0)+1,
                        message='Retrying the same upload after closing its empty composer; Share has not started.')
                    self._save();return self.get(job_id)
            if status == 'published':
                match = re.fullmatch(r'https://www\.instagram\.com/(?:([A-Za-z0-9._]+)/)?(?:reel|p)/[A-Za-z0-9_-]+/', url)
                if job['action'] != 'reel' or job['status'] != 'sharing' or account != job['account'] or not match or (match[1] and match[1].lower() != account):
                    raise ValueError('Publication lacks matching account and reel evidence.')
            if status == 'complete' and job['action'] not in ('inspect', 'preview'):
                raise ValueError('An upload needs an actual publication receipt.')
            job.update(status=status, account=account or job['account'], url=url if status == 'published' else '',
                       message=str(result.get('message', ''))[:500], finished=time.time())
            self.seen = time.time()
            self._save()
            return self.get(job_id)

    def cancel(self, job_id):
        with self.lock:
            job = next(j for j in self.data['jobs'] if j['id'] == job_id)
            job['stop'] = True
            if job['status'] == 'queued':
                job.update(status='cancelled', message='Cancelled before Chrome started.')
            self._save()
            return dict(job)

    def retire_stopped_youtube(self,job_id,session):
        """Explicit chat continuation preserves a stopped attempt as cancelled.

        Its replacement still reuses the remote upload ID. An attempt that
        crossed Schedule is never retired or replayed here.
        """
        with self.lock:
            job=next((j for j in self.data['jobs'] if j['id']==job_id),None)
            if (not job or job.get('session')!=session or job['action']!='youtube_schedule'
                or job['status'] not in ('needs_review','blocked') or not job.get('stop')
                or job.get('submission_started') is not False):return False
            job.update(status='cancelled',message='Stopped before Schedule. A new explicit continuation may reuse the existing upload.',updated=time.time())
            self._save();return True

    def retry_before_share(self, job_id):
        """Explicit owner retry only when durable state proves Share never started."""
        with self.lock:
            job = next((j for j in self.data['jobs'] if j['id'] == job_id), None)
            if not job or job['status'] != 'needs_review' or job.get('submission_started') is not False or job.get('last_phase') not in ('queued', 'running'):
                raise ValueError('This upload cannot be retried safely. Check Instagram; a submission may already have been sent.')
            if job['video']:
                stat = Path(job['video']).stat()
                if [stat.st_size, stat.st_mtime_ns] != job['file_stamp']:
                    raise ValueError('The video changed. Prepare the new export as a new request.')
            job.setdefault('attempts', []).append({'finished':job.get('finished'), 'message':job.get('message')})
            job.update(status='queued', last_phase='queued', stop=False, lease='', updated=time.time(),
                       message='Resuming the prepared upload; keeping its video, caption and account.')
            self._save()
            return dict(job)
