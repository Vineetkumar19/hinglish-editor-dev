"""Bounded public evidence for the voice assistant's informational turns."""
from html import unescape
import os
import re
from urllib.parse import quote, urlsplit

import requests


_EXPLICIT = re.compile(r'^(?:(?:please|can you|could you)\s+)?(?:look up|search(?: for| the web for)?|google|check online for|find online)\s+(.+)$', re.I)
_FRESH = re.compile(r'\b(?:latest|current(?:ly)?|today|right now|this week|live score)\b|आज|अभी|ताज़ा', re.I)
_PRIVATE = re.compile(r'https?://|\b[a-z]:[\\/]|@|\b(?:password|passcode|token|secret|my|mine|our|phone number|home address)\b|मेरा|मेरी|मेरे|पासवर्ड', re.I)


def lookup_query(question):
    if re.match(r"^(?:how are you|how(?:'s| is) it going|are you (?:doing|okay|well))\b", question.strip(), re.I):
        return '', False
    explicit = _EXPLICIT.fullmatch(question.strip(' .?!।'))
    query = explicit[1].strip() if explicit else question.strip(' .?!।')
    if not 2 <= len(query) <= 180 or _PRIVATE.search(query):
        return '', False
    return query, bool(explicit or _FRESH.search(query))


def _clean(value, limit):
    return ' '.join(unescape(re.sub(r'<[^>]+>', '', str(value or ''))).split())[:limit]


def public_evidence(query):
    if not query:
        return []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'StorylensVoice/1.0 (public factual lookup)'
        key = os.environ.get('FIRECRAWL_API_KEY', '').strip()
        if key:
            try:
                response = session.post('https://api.firecrawl.dev/v2/search',
                    headers={'Authorization': 'Bearer ' + key},
                    json={'query': query, 'sources': ['web'], 'limit': 3, 'timeout': 6000},
                    timeout=(3, 8), allow_redirects=False)
                response.raise_for_status()
                found = []
                for hit in response.json().get('data', {}).get('web', [])[:3]:
                    url = str(hit.get('url', ''))
                    parsed = urlsplit(url)
                    description = _clean(hit.get('description'), 500)
                    if parsed.scheme == 'https' and parsed.hostname and parsed.username is None and parsed.password is None and description:
                        found.append({'title': _clean(hit.get('title'), 120), 'url': url[:500], 'text': description})
                if found:
                    return found
            except (requests.RequestException, ValueError, AttributeError, TypeError):
                pass
        try:
            response = session.get('https://en.wikipedia.org/w/api.php', params={
                'action': 'query', 'generator': 'search', 'gsrsearch': query, 'gsrlimit': 3,
                'gsrnamespace': 0, 'prop': 'extracts|pageprops', 'exintro': 1,
                'explaintext': 1, 'exchars': 650, 'format': 'json', 'formatversion': 2,
            }, timeout=(3, 6), allow_redirects=False)
            response.raise_for_status()
            pages = response.json().get('query', {}).get('pages', [])
            return [{'title': _clean(page['title'], 120),
                     'url': 'https://en.wikipedia.org/wiki/' + quote(page['title'].replace(' ', '_'), safe=''),
                     'text': _clean(page['extract'], 650)}
                    for page in sorted(pages, key=lambda page: page.get('index', 999))
                    if page.get('extract') and 'disambiguation' not in page.get('pageprops', {})][:3]
        except (requests.RequestException, ValueError, AttributeError, KeyError, TypeError):
            return []
