"""Fetch fresh evidence; never equate a local model or a search hit with a verified fact."""
import copy
import json
import os
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests

from .profiles import Profiles, valid_profile

DOMAINS = ('icc-cricket.com', 'bcci.tv', 'iplt20.com', 'espncricinfo.com', 'cricbuzz.com',
           'cricket.or.jp', 'olympics.com', 'ecb.co.uk', 'cricket.com.au', 'nzc.nz',
           'pcb.com.pk', 'cricket.co.za', 'windiescricket.com', 'cricketireland.ie',
           'cricketscotland.com', 'kncb.nl', 'acc-cricket.com', 'en.wikipedia.org')


def allowed_url(url):
    p = urlparse(url)
    return p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443) and any(
        p.hostname == d or p.hostname == 'www.' + d for d in DOMAINS)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def get_page(session, url):
    for _ in range(4):
        if not allowed_url(url):
            raise ValueError('Use a public HTTPS page from an approved cricket source.')
        with session.get(url, timeout=(8, 18), stream=True, allow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            response.raise_for_status()
            if 'html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Choose a readable web article or scorecard.')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError('Source page is too large.')
            parser = Text()
            parser.feed(body.decode(response.encoding or 'utf-8', errors='replace'))
            content = ' '.join(parser.parts)
            if len(content) < 150:
                raise ValueError('Source needs JavaScript or has no readable evidence.')
            return {'url': url, 'text': content[:2200], 'kind': 'source excerpt',
                    'verification': 'unverified; confirm the relevant facts on the source page'}
    raise ValueError('Too many redirects from the source.')


def usable_context(receipt, now=None):
    receipt = copy.deepcopy(receipt)
    age = (time.time() if now is None else now) - receipt.get('retrieved_at', 0)
    receipt['age_minutes'] = round(max(0, age) / 60, 1)
    if age > 1800:
        receipt['sources'] = []
        receipt['matches'] = []
        receipt['warnings'] = ['Research is over 30 minutes old. Refresh it before using current match facts.']
    return receipt


def fetch(root, profile, progress=print, session=None):
    valid_profile(profile)
    card = Profiles(root).read()['profiles'][profile]
    topic = card.get('topic', '').strip()
    if not topic:
        raise ValueError('Enter a match, player or research topic first.')
    client = session or requests.Session()
    if session is None:
        client.trust_env = False
        client.headers['User-Agent'] = 'HinglishEditor/1.0 (creator research)'
    receipt = {'topic': topic, 'requested_match_id': card.get('match_id', '').strip(), 'retrieved_at': time.time(), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
               'sources': [], 'matches': [], 'warnings': [],
               'rule': 'No automatic fact verification. Confirm match identity/date and conflicts before publication.'}
    try:
        urls = card.get('source_urls', '').split()
        if len(urls) > 5 or any(not allowed_url(u) for u in urls):
            raise ValueError('Supply at most five HTTPS links from approved cricket sources.')
        for url in urls:
            progress('Reading a supplied cricket source')
            try:
                receipt['sources'].append(get_page(client, url))
            except (requests.RequestException, ValueError):
                receipt['warnings'].append('A supplied source was blocked or unreadable: ' + url)
        key = os.environ.get('BRAVE_SEARCH_API_KEY', '')
        if key:
            progress('Finding current source links')
            try:
                response = client.get('https://api.search.brave.com/res/v1/web/search',
                    headers={'X-Subscription-Token': key}, params={'q': topic, 'count': 10,
                    'freshness': 'pd', 'extra_snippets': 'true'}, timeout=(8, 20))
                response.raise_for_status()
                for hit in response.json().get('web', {}).get('results', []):
                    if allowed_url(hit.get('url', '')):
                        receipt['sources'].append({'title': hit.get('title', '')[:180], 'url': hit['url'],
                            'text': re.sub('<[^>]+>', '', str(hit.get('description', '')))[:1000],
                            'kind': 'search lead', 'verification': 'unverified snippet'})
            except (requests.RequestException, ValueError):
                receipt['warnings'].append('Search provider unavailable; no current search facts inferred.')
        elif not urls:
            receipt['warnings'].append('Add source links or configure BRAVE_SEARCH_API_KEY for internet discovery.')
        cricket_key = os.environ.get('CRICKETDATA_API_KEY', '')
        if profile == 'cricket' and cricket_key:
            match_id = card.get('match_id', '').strip()
            if match_id and not re.fullmatch(r'[A-Za-z0-9-]{1,100}', match_id):
                raise ValueError('Invalid CricketData match ID.')
            try:
                endpoint = 'match_info' if match_id else 'currentMatches'
                params = {'apikey': cricket_key, **({'id': match_id} if match_id else {'offset': 0})}
                response = client.get('https://api.cricapi.com/v1/' + endpoint, params=params, timeout=(8, 20))
                response.raise_for_status()
                answer = response.json()
                if answer.get('status') != 'success':
                    raise ValueError('Provider did not return match data')
                matches = [answer['data']] if match_id else answer.get('data', [])
                if match_id and (not isinstance(matches[0], dict) or matches[0].get('id') != match_id):
                    raise ValueError('Provider returned a different match ID')
                for match in matches[:25]:
                    receipt['matches'].append({k: match[k] for k in ('id', 'name', 'date', 'dateTimeGMT',
                        'status', 'teams', 'score', 'matchEnded', 'matchType', 'venue') if k in match})
                receipt['warnings'].append('CricketData is a third-party feed: coverage/delay varies. '
                    + ('Check this match ID, teams and date against an official scorecard.' if match_id else
                       'This is a candidate list, not a selected match. Save an exact match ID and refresh.'))
                receipt['score_feed'] = 'https://cricketdata.org/live-cricket-score-api/'
                receipt['selected_match_id'] = match_id
            except (requests.RequestException, ValueError, KeyError, TypeError):
                receipt['warnings'].append('CricketData feed unavailable; no scores were guessed.')
        elif profile == 'cricket':
            receipt['warnings'].append('CRICKETDATA_API_KEY is not configured. Use an official scorecard link for match facts.')
        receipt['sources'] = receipt['sources'][:12]
        folder = Path(root) / 'cache' / 'niche'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (profile + '-research.json')
        import uuid
        temporary = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
        return receipt
    finally:
        if session is None:
            client.close()
