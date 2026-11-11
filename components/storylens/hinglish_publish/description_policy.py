"""Owner channel links, enforced after model grounding and only on YouTube."""
import copy
import json
import re
from pathlib import Path


def policy(root, profile):
    path = Path(root) / 'config.workflow.local.json'
    data = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    return copy.deepcopy(data.get('youtube_description_policy', {}).get('profiles', {}).get(profile, {}))


def apply(root, profile, metadata, platform='youtube'):
    value = copy.deepcopy(metadata)
    if platform != 'youtube':
        return value
    links = policy(root, profile).get('links', [])
    if not links:
        return value
    description = str(value.get('description', '')).strip()
    # Preserve the existing final hashtag line and all viewer-facing prose.
    tail = re.search(r'(?:\s+|^)((?:#[\w]+[ \t]*)+)\s*$', description)
    hashtags = tail[1].strip() if tail else ''
    body = description[:tail.start()].rstrip() if tail else description
    missing = [f"{link['label']}: {link['url']}" for link in links
               if link['url'].rstrip('/').casefold() not in description.casefold()]
    if missing:
        description = '\n\n'.join(part for part in (body, '\n'.join(missing), hashtags) if part)
    if len(description) > 5000:
        raise ValueError('Shorten the YouTube description so its required channel links fit within 5,000 characters.')
    value['description'] = description
    return value
