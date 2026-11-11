"""Official publishing APIs. No password storage or browser-click automation."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import secrets

SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube.readonly']


class PreflightError(RuntimeError):
    """No remote publishing request was made; configuration needs attention."""


class YouTubeUploadRejected(PreflightError):
    """Google rejected session creation; no video bytes were transferred."""
    def __init__(self,error):
        try:
            body=json.loads(error.content)
            reason=body.get('error',{}).get('errors',[{}])[0].get('reason','unknown')
        except (ValueError,TypeError,IndexError,AttributeError):reason='unknown'
        if not isinstance(reason,str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}',reason):reason='unknown'
        status=getattr(getattr(error,'resp',None),'status',None)
        if not isinstance(status,int):status=None
        explanations={
            'uploadLimitExceeded':'YouTube has reached this channel\'s upload limit. Wait before retrying the remaining files.',
            'quotaExceeded':'The connected Google API project has exhausted its quota. Retry after quota is available.',
            'dailyLimitExceeded':'The connected Google API project has reached its daily limit. Retry after the limit resets.',
            'invalidTitle':'YouTube rejected the video title. Correct it before resuming.',
            'invalidDescription':'YouTube rejected the description. Correct it before resuming.',
            'invalidTags':'YouTube rejected the video tags. Correct them before resuming.',
            'insufficientPermissions':'The YouTube connection lacks upload permission. Reconnect the intended channel.'}
        detail=explanations.get(reason,'Google rejected the start of this upload. Review the reported error before retrying.')
        self.failure={'phase':'initializing','safe_retry':True,'http_status':status,'reason':reason}
        super().__init__(f'{detail} (HTTP {status or "unknown"}; {reason}). No video bytes were sent for this file.')


def youtube_client(root, profile='general'):
    from hinglish_niche.profiles import account_key
    key = account_key('youtube', profile)
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as error:
        raise PreflightError('Install requirements-publish.txt to connect YouTube') from error
    try:
        stored = secrets.load(root, key)
        credentials = Credentials.from_authorized_user_info(stored['credentials'], SCOPES)
        if not credentials.valid:
            credentials.refresh(Request())
            stored['credentials'] = json.loads(credentials.to_json())
            secrets.save(root, key, stored)
        return build('youtube', 'v3', credentials=credentials, cache_discovery=False), stored
    except Exception as error:
        raise PreflightError('YouTube account needs reconnection; no upload was started') from error


def connect_youtube(root, client_file='', profile='general', *, on_authorization=None):
    """Reconnect the same app/channel, keeping app secrets in memory and DPAPI."""
    from hinglish_niche.profiles import account_key
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    key = account_key('youtube', profile)
    try:
        previous = secrets.load(root, key)
    except FileNotFoundError:
        previous = {}
    except Exception as error:
        raise ValueError('The saved YouTube connection could not be read. Keep it and check the local account settings before reconnecting.') from error
    stored = previous.get('credentials', {})
    scopes = stored.get('scopes') or SCOPES
    if isinstance(scopes, str):scopes = scopes.split()
    if set(scopes) != set(SCOPES):
        raise ValueError('The saved YouTube permissions differ. Check this connection before changing its access.')
    value = str(client_file or '').strip().strip(chr(34))
    if value:
        path = Path(value)
        if not path.is_file() or path.suffix.lower() != '.json':
            raise ValueError('Choose the Google desktop client JSON file, or leave this optional field empty to reconnect the saved account.')
        config = json.loads(path.read_text('utf-8-sig'))
        selected = config.get('installed') or config.get('web') or {}
        if stored.get('client_id') and selected.get('client_id') and selected['client_id'] != stored['client_id']:
            raise ValueError('This file belongs to a different Google app. Leave the field empty to reconnect using the saved app.')
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
    elif stored.get('client_id') and stored.get('client_secret'):
        # Do not write a decrypted client-secret JSON beside the encrypted token.
        # Reuse the app already authorized for this existing profile.
        config = {'installed': {'client_id': stored['client_id'], 'client_secret': stored['client_secret'],
                  'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                  'token_uri': 'https://oauth2.googleapis.com/token',
                  'redirect_uris': ['http://127.0.0.1']}}
        flow = InstalledAppFlow.from_client_config(config, SCOPES)
    else:
        raise ValueError('No saved Google app configuration is available. Choose the original Google desktop OAuth client JSON file for first-time setup.')
    original_authorization_url = flow.authorization_url
    if on_authorization is not None:
        def authorization_url(*args, **kwargs):
            result = original_authorization_url(*args, **kwargs)
            on_authorization(result[0])
            return result
        flow.authorization_url = authorization_url
    try:
        credentials = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=180,
                                           open_browser=on_authorization is None,
                                           authorization_prompt_message=None,
                                           prompt='select_account consent', access_type='offline')
    except Exception as error:
        if type(error).__name__ == 'WSGITimeoutError':
            raise ValueError('Google sign-in timed out. Click Sign in with Google to try again.') from error
        if type(error).__name__ == 'AccessDeniedError':
            raise ValueError('Google sign-in was declined. Check the Google access message, then try again.') from error
        raise
    finally:
        flow.authorization_url = original_authorization_url
    client = build('youtube', 'v3', credentials=credentials, cache_discovery=False)
    try:
        channels = client.channels().list(part='snippet', mine=True).execute().get('items', [])
        if len(channels) != 1:
            raise ValueError('Select exactly one YouTube channel during sign-in')
        channel = channels[0]
        if previous.get('channel_id') and channel['id'] != previous['channel_id']:
            raise ValueError('Google selected a different channel. Reconnect the same '+str(previous.get('name') or profile)+' channel. Your existing saved connection was kept.')
        if not getattr(credentials, 'refresh_token', None):
            raise ValueError('Google did not return a renewable sign-in. Reconnect the same channel and complete the Google permission screen; the previous connection was kept.')
        secrets.save(root, key, {'credentials': json.loads(credentials.to_json()),
                                     'channel_id': channel['id'], 'name': channel['snippet']['title']})
        return {'name': channel['snippet']['title'], 'channel_id': channel['id']}
    finally:
        close = getattr(client, 'close', None)
        if close:close()


def connect_instagram(root, token, account_id, version='v25.0', profile='general'):
    from hinglish_niche.profiles import account_key
    key = account_key('instagram', profile)
    if not re.fullmatch(r'v\d+\.\d+', version):
        raise ValueError('Use a supported Meta API version, for example v25.0')
    if not str(account_id).isdigit() or not token.strip():
        raise ValueError('Enter your Instagram professional account ID and access token')
    response = requests.get(f'https://graph.instagram.com/{version}/{account_id}',
                            headers={'Authorization': 'Bearer ' + token.strip()},
                            params={'fields': 'id,username'}, timeout=30)
    if not response.ok:
        raise ValueError('Instagram could not verify the account; check the ID, token and permissions')
    data = response.json()
    if str(data.get('id')) != str(account_id):
        raise ValueError('Instagram account ID does not match')
    secrets.save(root, key, {'token': token.strip(), 'account_id': str(account_id),
                                    'version': version, 'name': data.get('username', '')})
    return {'name': data.get('username', ''), 'account_id': str(account_id)}


class YouTube:
    def __init__(self, root, config):
        self.root, self.config = root, config

    def publish(self, job, checkpoint):
        if job['visibility'] == 'public' and not self.config.get('youtube_public_api_ready'):
            raise PreflightError('Public YouTube API uploads require a compliant, audited API project. '
                                 'Connect an approved project or use private uploads for testing.')
        client, account = youtube_client(self.root, job.get('profile', 'general'))
        if account['channel_id'] != job.get('account_id'):
            raise PreflightError('The connected YouTube channel changed; review and authorize this item again')
        from googleapiclient.http import MediaFileUpload
        metadata, remote = job['metadata'], dict(job.get('remote') or {})
        if not remote.get('id'):
            status = {'privacyStatus': job['visibility'], 'selfDeclaredMadeForKids': job['made_for_kids'],
                      'containsSyntheticMedia': job['synthetic_media']}
            if job['visibility'] == 'public' and job['due'] > time.time() + 60:
                status.update(privacyStatus='private', publishAt=datetime.fromtimestamp(
                    job['due'], timezone.utc).isoformat())
            request = client.videos().insert(part='snippet,status', body={
                'snippet': {'title': metadata['title'], 'description': metadata['description'],
                            'tags': metadata['tags'], 'categoryId': {'gaming': '20', 'cricket': '17'}.get(job.get('profile'), '22')}, 'status': status},
                media_body=MediaFileUpload(job['video'], chunksize=8 * 1024 * 1024, resumable=True))
            if job.get('prepare_post_id') and job.get('id'):
                from .youtube_upload import Session
                result=Session(self.root,job).run(request,getattr(checkpoint,'progress',None))
            else:
                result = None
                while result is None:
                    try:
                        _, result = request.next_chunk(num_retries=0)
                    except Exception as error:
                        from googleapiclient.errors import ResumableUploadError
                        if isinstance(error,ResumableUploadError):
                            raise YouTubeUploadRejected(error) from error
                        raise
            remote.update(id=result['id'], url='https://www.youtube.com/watch?v=' + result['id'])
            checkpoint(remote)
        if job.get('thumbnail') and not remote.get('thumbnail_done'):
            client.thumbnails().set(videoId=remote['id'], media_body=MediaFileUpload(
                job['thumbnail'], mimetype='image/jpeg')).execute()
            remote['thumbnail_done'] = True
            checkpoint(remote)
        result = client.videos().list(part='status,processingDetails', id=remote['id']).execute()
        items = result.get('items', [])
        if not items:
            raise RuntimeError('The uploaded video could not yet be verified')
        status = items[0]['status']
        if status.get('uploadStatus') in ('failed', 'rejected', 'deleted'):
            raise RuntimeError('YouTube did not accept this video')
        remote['privacy'] = status.get('privacyStatus')
        if status.get('publishAt') and job['visibility'] == 'public':
            return remote, 'scheduled'
        if status.get('privacyStatus') == 'public' and status.get('uploadStatus') == 'processed':
            return remote, 'published'
        if job['visibility'] == 'private':
            return remote, 'uploaded_private'
        if status.get('privacyStatus') != 'public':
            raise RuntimeError('YouTube kept the video private. Check API project audit and channel restrictions.')
        return remote, 'processing'

    def verify(self, job):
        client, account = youtube_client(self.root, job.get('profile', 'general'))
        if account['channel_id'] != job.get('account_id'):
            raise PreflightError('The connected YouTube channel changed')
        data = client.videos().list(part='status', id=job['remote']['id']).execute().get('items', [])
        if not data:
            raise RuntimeError('YouTube video unavailable')
        status = data[0]['status']
        if status.get('uploadStatus') in ('failed', 'rejected', 'deleted'):
            raise RuntimeError('YouTube rejected or removed the uploaded video')
        if status.get('privacyStatus') == 'public' and status.get('uploadStatus') == 'processed':
            return 'published'
        if status.get('privacyStatus') == 'private' and not status.get('publishAt'):
            raise RuntimeError('YouTube upload is private without a future schedule; review it in Studio')
        return job['status']


class Instagram:
    def __init__(self, root, config):
        self.root = root

    def publish(self, job, checkpoint):
        # URL-based media ingestion is documented for both Instagram login paths.
        # Local E:\ files are not internet URLs; the creator must supply hosted media.
        media_url = job.get('video_url', '')
        parsed = urlparse(media_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname in ('localhost', '127.0.0.1'):
            raise PreflightError('Instagram needs a publicly reachable HTTPS URL for this video. '
                                 'Add video_url to its .publish.json sidecar.')
        try:
            from hinglish_niche.profiles import account_key
            account = secrets.load(self.root, account_key('instagram', job.get('profile', 'general')))
        except Exception as error:
            raise PreflightError('Connect your Instagram professional account first') from error
        if account['account_id'] != job.get('account_id'):
            raise PreflightError('The connected Instagram account changed; review and authorize this item again')
        base = 'https://graph.instagram.com/' + account['version']
        headers = {'Authorization': 'Bearer ' + account['token']}
        remote = dict(job.get('remote') or {})

        def call(method, endpoint, **kwargs):
            response = requests.request(method, base + '/' + endpoint, headers=headers, timeout=90, **kwargs)
            if not response.ok:
                # Do not echo request URLs, tokens or raw response bodies into logs.
                raise RuntimeError(f'Instagram API rejected the request (HTTP {response.status_code})')
            return response.json()

        if not remote.get('container'):
            data = call('POST', account['account_id'] + '/media', data={
                'media_type': 'REELS', 'video_url': media_url,
                'caption': job['metadata']['instagram_caption'], 'share_to_feed': 'true'})
            remote['container'] = data['id']
            checkpoint(remote)
        if not remote.get('id'):
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                data = call('GET', remote['container'], params={'fields': 'status_code'})
                if data.get('status_code') == 'FINISHED':
                    break
                if data.get('status_code') in ('ERROR', 'EXPIRED', 'PUBLISHED'):
                    raise RuntimeError('Instagram container needs review; do not publish it a second time')
                time.sleep(10)
            else:
                raise RuntimeError('Instagram processing exceeded ten minutes; the saved container needs review')
            data = call('POST', account['account_id'] + '/media_publish', data={'creation_id': remote['container']})
            remote['id'] = data['id']
            checkpoint(remote)
        data = call('GET', remote['id'], params={'fields': 'id,permalink'})
        if str(data.get('id')) != str(remote['id']):
            raise RuntimeError('Instagram publication has not been verified')
        remote['url'] = data.get('permalink', '')
        checkpoint(remote)
        return remote, 'published'
