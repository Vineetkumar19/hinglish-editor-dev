"""Read-only, account-bound sources for the StoryLens analytics dashboard."""
import json
import re
from calendar import monthrange
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from hinglish_publish import secrets


ACCOUNTS = {
    'youtube-cricket': ('youtube', 'cricket', 'Fantasy Legends', 'UCISO1Vfw20A6Tlb2xMGQqGg'),
    'youtube-gaming': ('youtube', 'gaming', 'Vineet Kumar', 'UCtc3vpF9QPHAM7lTYCCulyg'),
    'instagram-cricket': ('instagram', 'cricket', '@fantasy_legends91', 'fantasy_legends91'),
    'instagram-gaming': ('instagram', 'gaming', '@vineet_editz19', 'vineet_editz19'),
}
READ = 'https://www.googleapis.com/auth/youtube.readonly'
ACTIVITY = 'https://www.googleapis.com/auth/yt-analytics.readonly'
MONEY = 'https://www.googleapis.com/auth/yt-analytics-monetary.readonly'
YT_DATA = 'https://www.googleapis.com/youtube/v3'
YT_REPORT = 'https://youtubeanalytics.googleapis.com/v2/reports'
IST = timezone(timedelta(hours=5, minutes=30))
YT_ACTIVITY = {'views': 'views', 'likes': 'likes', 'comments': 'comments', 'shares': 'shares',
               'estimatedMinutesWatched': 'watch_minutes', 'subscribersGained': 'gained',
               'subscribersLost': 'lost'}



class SourceError(Exception):
    pass


def get(session, url, params):
    try:
        response = session.get(url, params=params, timeout=15, allow_redirects=False)
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise SourceError('The platform did not return data. Try refreshing again.') from error
    if not isinstance(body, dict):
        raise SourceError('The platform returned an unreadable report.')
    if not response.ok or 'error' in body:
        error = body.get('error', {})
        errors = error.get('errors') or [{}]
        reason = errors[0].get('reason') or error.get('status') or error.get('code') or ''
        safe = str(reason) if re.fullmatch(r'[A-Za-z0-9_]{1,50}', str(reason)) else ''
        if response.status_code in (401, 403) or reason in (10, 190, 200):
            raise SourceError(f'Platform access needs checking (HTTP {response.status_code}, {safe or "authorization"}).')
        if response.status_code == 429:
            raise SourceError('The platform rate-limited this refresh. Saved results are still available.')
        raise SourceError(f'The platform did not provide this report (HTTP {response.status_code}, {safe or "unavailable"}).')
    return body


def mapped(data, keys):
    values = {}
    for source, target in keys.items():
        value = data.get(source)
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if type(value) in (int, float):
            values[target] = value
    return values


def yt_session(credentials):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials

    return AuthorizedSession(Credentials.from_authorized_user_info(credentials), refresh_timeout=15)


def yt_channel(session, expected):
    rows = get(session, YT_DATA + '/channels', {'part': 'snippet,statistics,contentDetails', 'mine': 'true'}).get('items', [])
    if [item.get('id') for item in rows] != [expected]:
        raise SourceError('The Google connection returned a different YouTube channel.')
    return rows[0]


def yt_connect(root, account, monetary):
    from google_auth_oauthlib.flow import InstalledAppFlow

    original = secrets.load(root, account)['credentials']
    config = {'installed': {'client_id': original['client_id'], 'client_secret': original['client_secret'],
                            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                            'token_uri': 'https://oauth2.googleapis.com/token',
                            'redirect_uris': ['http://127.0.0.1']}}
    scopes = [READ, ACTIVITY] + ([MONEY] if monetary else [])
    flow = InstalledAppFlow.from_client_config(config, scopes)
    credentials = flow.run_local_server(host='127.0.0.1', port=0, timeout_seconds=180,
                                        prompt='select_account consent', access_type='offline',
                                        authorization_prompt_message=None)
    granted = set(credentials.granted_scopes or credentials.scopes or [])
    if not set(scopes).issubset(granted) or not credentials.refresh_token:
        raise SourceError('Google did not provide the requested renewable read permissions.')
    info = json.loads(credentials.to_json())
    expected = ACCOUNTS[account][3]
    with closing(yt_session(info)) as session:
        yt_channel(session, expected)
    secrets.save(root, 'analytics-' + account, {'credentials': info, 'account_id': expected,
                                               'monetary': MONEY in granted})


def yt_report(session, expected, start, end, dimension, metrics, video=None):
    params = {'ids': 'channel==' + expected, 'startDate': str(start), 'endDate': str(end),
              'metrics': ','.join(metrics)}
    if dimension:
        params['dimensions'] = dimension
    if video:
        params['filters'] = 'video==' + video
    if dimension == 'video':
        params.update(sort='-views' if 'views' in metrics else '-estimatedRevenue', maxResults=200)
    if 'estimatedRevenue' in metrics:
        params['currency'] = 'INR'
    body = get(session, YT_REPORT, params)
    names = [column['name'] for column in body.get('columnHeaders', [])]
    for raw in body.get('rows', []):
        row = dict(zip(names, raw))
        yield (row[dimension] if dimension else None), mapped(row, metrics)


def yt_video_detail(root, account, video, published):
    try:
        grant = secrets.load(root, 'analytics-' + account)
    except RuntimeError:
        return {'lifetime': {}, 'daily': {}, 'notes': ['Connect YouTube Analytics for watch time and subscriber attribution.']}
    expected = ACCOUNTS[account][3]
    if grant.get('account_id') != expected:
        raise SourceError('The saved Analytics connection does not match this channel.')
    end = datetime.now(ZoneInfo('America/Los_Angeles')).date() - timedelta(days=1)
    start = date.fromisoformat(published[:10]) if published else date(2005, 4, 23)
    lifetime, daily, notes = {}, {}, []
    if start > end:
        return {'lifetime': lifetime, 'daily': daily, 'notes': ['YouTube has not closed the first reporting day for this video.']}
    with closing(yt_session(grant['credentials'])) as session:
        yt_channel(session, expected)
        try:
            lifetime.update(next(yt_report(session, expected, start, end, None, YT_ACTIVITY, video), (None, {}))[1])
            daily.update(yt_report(session, expected, max(start, end - timedelta(days=13)), end, 'day', YT_ACTIVITY, video))
        except SourceError as error:
            notes.append('Activity report. ' + str(error))
        if grant.get('monetary'):
            try:
                lifetime.update(next(yt_report(session, expected, start, end, None, {'estimatedRevenue': 'revenue'}, video), (None, {}))[1])
            except SourceError as error:
                notes.append('Revenue report. ' + str(error))
        else:
            notes.append('Estimated revenue needs the monetary read permission.')
    return {'lifetime': lifetime, 'daily': daily, 'notes': notes, 'requested_through': str(end)}


def yt_catalogue(session, channel, expected, emit):
    playlist = channel['contentDetails']['relatedPlaylists']['uploads']
    cursor = None
    count = 0
    for _ in range(20):
        params = {'part': 'contentDetails', 'playlistId': playlist, 'maxResults': 50}
        if cursor:
            params['pageToken'] = cursor
        page = get(session, YT_DATA + '/playlistItems', params)
        ids = [item['contentDetails']['videoId'] for item in page.get('items', [])]
        if ids:
            rows = get(session, YT_DATA + '/videos', {'part': 'snippet,statistics', 'id': ','.join(ids)}).get('items', [])
            for row in rows:
                snippet = row.get('snippet', {})
                if snippet.get('channelId') != expected:
                    continue
                stats = mapped(row.get('statistics', {}), {'viewCount': 'views', 'likeCount': 'likes', 'commentCount': 'comments'})
                emit(row['id'], {'title': snippet.get('title', ''), 'published': snippet.get('publishedAt', ''), **stats})
                count += 1
        cursor = page.get('nextPageToken')
        if not cursor:
            break
    return count, bool(cursor)


def collect_youtube(root, account, today, months, start, emit):
    expected = ACCOUNTS[account][3]
    warnings = []
    try:
        grant = secrets.load(root, 'analytics-' + account)
    except RuntimeError:
        grant = None
    saved = grant or secrets.load(root, account)
    if (saved.get('account_id') if grant else saved.get('channel_id')) != expected:
        raise SourceError('The saved YouTube connection does not match this dashboard account.')
    with closing(yt_session(saved['credentials'])) as session:
        channel = yt_channel(session, expected)
        stats = mapped(channel['statistics'], {'subscriberCount': 'audience', 'viewCount': 'views', 'videoCount': 'posts'})
        if channel['statistics'].get('hiddenSubscriberCount'):
            stats.pop('audience', None)
        emit('snapshot', today, '', stats)
        try:
            _, capped = yt_catalogue(session, channel, expected, lambda key, value: emit('content', today, key, value))
            if capped:
                warnings.append('The upload list is limited to the most recent 1,000 videos.')
        except SourceError as error:
            warnings.append('Video counters. ' + str(error))
        if not grant:
            return 'counters', ['Connect YouTube Analytics for historical views, watch time, shares and subscriber activity.', *warnings]
        end = datetime.now(ZoneInfo('America/Los_Angeles')).date() - timedelta(days=1)
        reports = [('activity', YT_ACTIVITY)]
        activity_ready = False
        if grant['monetary']:
            reports.append(('revenue', {'estimatedRevenue': 'revenue'}))
        else:
            warnings.append('Estimated revenue needs the separate monetary read permission.')
        for kind, metrics in reports:
            try:
                for key, stats in yt_report(session, expected, start, end, 'day', metrics):
                    emit(kind, key, '', stats)
                if kind == 'activity':
                    activity_ready = True
            except SourceError as error:
                warnings.append(('Revenue' if kind == 'revenue' else 'Analytics') + '. ' + str(error))
                continue
            for month in months:
                first = date.fromisoformat(month + '-01')
                last = min(end, first.replace(day=monthrange(first.year, first.month)[1]))
                if last < first:
                    continue
                try:
                    for key, stats in yt_report(session, expected, first, last, 'video', metrics):
                        emit('video_' + kind, month, key, stats)
                except SourceError as error:
                    warnings.append(f'Video report for {month}. {error}')
                    break
    return ('analytics' if activity_ready else 'counters'), warnings
