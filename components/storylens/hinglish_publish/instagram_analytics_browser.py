"""Validation for analytics-only receipts from the paired Chrome extension."""
import re


ACTION = 'instagram_analytics_read'
PROFILE_FIELDS = {'audience', 'following', 'posts'}
ROLLING_FIELDS = {'views', 'reach', 'interactions', 'accounts_engaged', 'profile_views', 'link_taps'}
REEL_FIELDS = {'grid_views', 'views', 'reach', 'interactions', 'likes', 'comments', 'saves', 'shares', 'gained'}


def counts(values, keys):
    if not isinstance(values, dict) or set(values) - keys or any(type(v) is not int or not 0 <= v < 2**53 for v in values.values()):
        raise ValueError('Chrome returned invalid Instagram counters.')
    return values


def receipt(job, result, accounts):
    if (job.get('stop') or job.get('submission_started') or result.get('account') != job['account'] or
            accounts.get(job['profile']) != job['account']):
        raise ValueError('Chrome did not verify the requested Instagram account.')
    snapshot = counts(result.get('snapshot'), PROFILE_FIELDS)
    rolling = counts(result.get('rolling'), ROLLING_FIELDS)
    content = result.get('content')
    notes = result.get('notes')
    if not snapshot or not isinstance(content, list) or len(content) > 25 or not isinstance(notes, list) or len(notes) > 4:
        raise ValueError('Chrome returned an incomplete Instagram analytics receipt.')
    seen = set()
    validated = []
    for item in content:
        if not isinstance(item, dict):
            raise ValueError('Chrome returned an invalid Reel row.')
        code = item.get('id')
        title = item.get('title')
        if (not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', code) or code in seen or
                not isinstance(title, str) or len(title) > 160):
            raise ValueError('Chrome returned an invalid Instagram Reel identity.')
        seen.add(code)
        metrics = counts({key: value for key, value in item.items() if key not in ('id', 'title')}, REEL_FIELDS)
        validated.append({'id': code, 'title': title, **metrics})
    if any(not isinstance(note, str) or len(note) > 260 for note in notes):
        raise ValueError('Chrome returned an invalid Instagram analytics notice.')
    return {'snapshot': snapshot, 'rolling': rolling, 'content': validated, 'notes': notes}
