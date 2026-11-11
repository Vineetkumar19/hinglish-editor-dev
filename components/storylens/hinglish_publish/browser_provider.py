"""Instagram publisher transport backed by the existing bounded Chrome queue."""
from pathlib import Path
import re
from .providers import PreflightError


class ConnectorOffline(PreflightError):
    """No side effect was attempted; keep the due item queued until reconnect."""

class BrowserInstagram:
    def __init__(self,bridge):self.bridge=bridge

    def _saved(self,job):
        snapshot=self.bridge.snapshot()
        account=snapshot.get('accounts',{}).get(job.get('profile','general'))
        if not account or account!=job.get('account_id'):
            raise PreflightError('The saved Instagram account changed. Review this draft; it was not sent to another account.')
        return snapshot,account

    def _receipt(self,job,remote):
        receipt=self.bridge.get(remote['browser_job_id'])
        if (receipt.get('action')!='reel' or receipt.get('account')!=job.get('account_id')
            or Path(receipt.get('video','')).resolve()!=Path(job['video']).resolve()):
            raise PreflightError('The saved Instagram task does not match this video and account. Check its receipt before retrying.')
        return receipt

    def publish(self,job,checkpoint):
        snapshot,account=self._saved(job)
        if not job.get('authorized_at'):
            raise PreflightError('Review and authorize this exact Instagram draft before posting.')
        remote=dict(job.get('remote') or {})
        if remote.get('browser_job_id'):
            self._receipt(job,remote)
            return remote,self.verify({**job,'remote':remote})
        if not snapshot.get('connected'):
            raise ConnectorOffline('Waiting for Chrome with Storylens Local Publisher connected. This Reel is still queued; no upload was attempted.')
        queued=self.bridge.enqueue('reel',account,job['video'],job['metadata']['instagram_caption'],
                                  authorized=True,reference='publisher:'+job.get('profile','general')+':'+job['id'])
        remote.update(browser_job_id=queued['id'],account=account,transport='browser')
        checkpoint(remote)
        # Queueing, account checks and a composer are never publication evidence.
        return remote,self.verify({**job,'remote':remote})

    def verify(self,job):
        remote=job.get('remote') or {}
        receipt=self._receipt(job,remote)
        status=receipt.get('status')
        if status=='published':
            url=receipt.get('url','')
            if not re.fullmatch(r'https://www\.instagram\.com/(?:'+re.escape(job['account_id'])+r'/)?(?:reel|p)/[A-Za-z0-9_-]+/',url):
                raise ValueError('Instagram publication is missing a matching post link.')
            job['remote'].update(url=url)
            return 'published'
        if status in ('queued','running','sharing'):return 'processing'
        if status=='cancelled' and receipt.get('submission_started') is False:return 'cancelled'
        raise ValueError('Instagram needs attention. Check the saved browser task and its receipt; no second upload was started.')
