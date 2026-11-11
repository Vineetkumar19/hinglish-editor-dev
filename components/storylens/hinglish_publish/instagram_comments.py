"""Instagram comment handoff for the existing Chrome Local Publisher."""

from datetime import datetime, timezone
import re
import time
from urllib.parse import urlsplit

from .comment_window import reply_cutoff



ACCOUNTS = {
    'cricket': 'fantasy_legends91',
    'gaming': 'vineet_editz19',
}
POST_PATH = re.compile(r'/(?:(?P<owner>[A-Za-z0-9._]{1,30})/)?(?P<post>(?:p|reel)/(?P<id>[A-Za-z0-9_-]{1,64}))/?')
COMMENT_ID = re.compile(r'[0-9]{1,30}')
HANDLE = re.compile(r'[A-Za-z0-9._]{1,30}')


def owned_post_id(account, source_url):
    if not isinstance(source_url, str):
        return None
    url = urlsplit(source_url)
    post = POST_PATH.fullmatch(url.path)
    if (url.scheme == 'https' and url.netloc == 'www.instagram.com'
            and not url.query and not url.fragment and post and post['owner'] == account):
        return post['id']
    return None


def validate_rows(account, rows, *, empty_source=None):
    if rows == [] and isinstance(empty_source, str):
        url = urlsplit(empty_source)
        post = POST_PATH.fullmatch(url.path)
        if (url.scheme == 'https' and url.netloc == 'www.instagram.com'
                and not url.query and not url.fragment and post and post['owner'] == account):
            return []
        raise ValueError('Chrome did not verify the empty Instagram post belongs to this account.')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
        raise ValueError('Chrome did not return a bounded Instagram comment batch.')
    validated = []
    keys = set()
    sources = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Chrome returned an invalid Instagram comment.')
        comment_id, source_id = row.get('comment_id'), row.get('source_id')
        author, text = row.get('author_id'), row.get('text')
        source_url, published_at = row.get('source_url'), row.get('published_at')
        source_title, source_description = row.get('source_title'), row.get('source_description')
        if not all(isinstance(value, str) for value in (
            comment_id, source_id, author, text, source_url, published_at, source_title, source_description
        )):
            raise ValueError('Instagram comment fields must be text.')
        url = urlsplit(source_url)
        post = POST_PATH.fullmatch(url.path)
        if (url.scheme != 'https' or url.netloc != 'www.instagram.com' or url.query or url.fragment
            or not post or post['owner'] != account or post['id'] != source_id
            or not COMMENT_ID.fullmatch(comment_id) or not HANDLE.fullmatch(author)
            or not text.strip() or len(text)>2200 or len(source_title)>140 or len(source_description)>2200):
            raise ValueError('Chrome did not verify the exact Instagram post and comment.')
        parsed = datetime.fromisoformat(published_at)
        if parsed.tzinfo is None or parsed.timestamp() > time.time() + 300:
            raise ValueError('The Instagram comment timestamp is invalid.')
        sources.add(source_url)
        if len(sources) != 1 or comment_id in keys:
            raise ValueError('Instagram comment identities are ambiguous.')
        keys.add(comment_id)
        validated.append(dict(comment_id=comment_id, source_id=source_id, source_url=source_url,
            author_id=author.lower(), text=text, published_at=parsed.astimezone(timezone.utc).isoformat(),
            source_title=source_title, source_description=source_description, own=author.lower()==account))
    return validated


class InstagramComments:
    def __init__(self, browser=None):
        self.browser = browser

    def connect(self, profile, account_id):
        status = self.check(profile, account_id)
        if not status['write_ready']:
            raise ValueError(status['blocker'])
        self._wait(self.browser.enqueue_comment_action(profile, account_id, 'instagram_comment_posts'))

    def check(self, profile, account_id):
        manual_url = self.manual_handoff(profile, account_id)
        bridge = self.browser.snapshot() if self.browser is not None else {}
        supports = bridge.get('supports', ())
        blocker = ''
        read_ready = write_ready = False
        if not bridge.get('connected'):
            blocker = 'Connect the signed-in Storylens Chrome extension.'
        elif bridge.get('accounts', {}).get(profile) != account_id:
            blocker = 'The Chrome publisher has a different saved Instagram account for this profile.'
        elif 'instagram_comments_read' not in supports:
            blocker = 'Reload the Storylens Chrome extension to enable comment reading.'
        else:
            read_ready = True
            write_ready = {'instagram_comments_reply', 'instagram_comments_window'}.issubset(supports)
            if not write_ready:
                blocker = 'Reload Storylens Local Publisher in Chrome to enable automatic replies.'
        return {'read_ready': read_ready, 'write_ready': write_ready, 'blocker': blocker,
                'manual_url': manual_url}

    def manual_handoff(self, profile, account_id, source_url=''):
        """Return a safe browser destination for owner review of the account or post."""
        if profile not in ACCOUNTS or ACCOUNTS[profile] != account_id:
            raise ValueError('Choose the exact saved Cricket or Gaming Instagram account.')
        if not source_url:
            return f'https://www.instagram.com/{account_id}/'
        url = urlsplit(str(source_url).strip())
        post = POST_PATH.fullmatch(url.path)
        if url.scheme != 'https' or url.netloc.lower() not in ('instagram.com', 'www.instagram.com') or not post or post['owner'] not in (None, account_id):
            raise ValueError('Use an exact Instagram post or Reel permalink.')
        owner = f'{account_id}/' if post['owner'] else ''
        return f"https://www.instagram.com/{owner}{post['post']}/"

    def _wait(self, job_id, *, submission=False):
        deadline = time.monotonic() + 150
        job = None
        try:
            while time.monotonic() < deadline:
                job = self.browser.get(job_id)
                if job['status'] == 'complete':
                    return job
                if job['status'] not in ('queued', 'running', 'sharing'):
                    break
                time.sleep(.25)
        finally:
            job = self.browser.discard_comment_read(job_id) or job
        error = ((job or {}).get('message') or 'Chrome did not finish the Instagram comment task.')
        if submission and not (job or {}).get('submission_started'):
            from hinglish_app.social_comments import CommentChanged, SubmissionDeferred
            if error == 'This comment already has a creator reply.':
                raise CommentChanged(error)
            raise SubmissionDeferred(error)
        raise RuntimeError(error)

    def scan(self, profile, account_id, since):
        status = self.check(profile, account_id)
        if not status['read_ready']:
            raise RuntimeError(status['blocker'])
        if status['write_ready']:
            cutoff = reply_cutoff(datetime.now(timezone.utc))
            found = self._wait(self.browser.enqueue_comment_action(profile, account_id, 'instagram_comment_posts'))
            rows = []
            failures = []
            expired = self.browser.expired_comment_posts(account_id, cutoff)
            for source in found['posts']:
                if owned_post_id(account_id, source) in expired:
                    continue
                try:
                    job = self.browser.enqueue_comment_action(profile, account_id, 'instagram_comments_read',
                                                              source_url=source, cutoff=cutoff.isoformat())
                    rows.extend(self._wait(job)['comments'])
                except (RuntimeError, ValueError) as error:
                    failures.append(str(error))
            return CommentScan(rows, failures)
        raise RuntimeError(status['blocker'])

    def preflight(self, profile, account_id, row):
        return bool(COMMENT_ID.fullmatch(row['comment_id']) and
                    self.manual_handoff(profile, account_id, row['source_url']))

    def send(self, profile, account_id, row, text, *, authorize):
        job = self.browser.enqueue_comment_action(profile, account_id, 'instagram_comments_reply',
            source_url=row['source_url'], comment_id=row['comment_id'], author=row['author_id'],
            comment_text=row['text'], reply_text=text, authorize=authorize)
        return self._wait(job, submission=True)['reply_id']


class CommentScan(list):
    def __init__(self, rows, failures):
        super().__init__(rows)
        self.warning = (f'{len(failures)} Instagram post(s) could not be checked. {failures[0]}'
                        if failures else None)
