"""One visible Google sign-in per profile, independent of media preparation."""
import os
import threading
import time
import uuid
from urllib.parse import urlsplit


def valid_google_url(value):
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname == 'accounts.google.com'
                and not url.username and not url.password and url.port in (None, 443)
                and url.path in ('/o/oauth2/auth', '/o/oauth2/v2/auth') and not url.fragment)
    except (TypeError, ValueError):
        return False


def start(publisher, client_file='', profile='general'):
    from hinglish_niche.profiles import valid_profile
    valid_profile(profile)
    ready = threading.Event()
    with publisher.lock:
        for task in publisher.tasks.values():
            if task.get('kind') == 'youtube_signin' and task.get('profile') == profile and task['status'] == 'working':
                return {'id': task['id'], **({'authorization_url': task['authorization_url']} if task.get('authorization_url') else {})}
        key = uuid.uuid4().hex[:12]
        task = {'id': key, 'kind': 'youtube_signin', 'profile': profile,
                'status': 'working', 'message': 'Opening Google sign-in…',
                'request': None, 'owner_pid': os.getpid(), 'created_at': time.time()}
        publisher.tasks[key] = task

    def authorization(url):
        if not valid_google_url(url):
            raise ValueError('The Google sign-in address could not be verified. Check the saved Google app configuration.')
        with publisher.lock:
            task.update(authorization_url=url, message='Google sign-in is ready. Complete it in your browser.')
        ready.set()

    def run():
        try:
            from .providers import connect_youtube
            result = connect_youtube(publisher.root, client_file, profile, on_authorization=authorization)
            with publisher.lock:
                task.update(status='done', result=result, message='YouTube connection saved for this profile.')
        except Exception as error:
            from hinglish_app.user_messages import failure
            issue = failure(error, feature='YouTube sign-in')
            with publisher.lock:
                task.update(status='failed', message=issue['error'], **issue)
        finally:
            with publisher.lock:
                task.pop('authorization_url', None)
            ready.set()

    threading.Thread(target=run, name='youtube-signin-' + profile, daemon=True).start()
    ready.wait(.75)
    with publisher.lock:
        return {'id': key, **({'authorization_url': task['authorization_url']} if task.get('authorization_url') else {})}
