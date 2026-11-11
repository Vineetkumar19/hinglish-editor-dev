"""Durable, bounded Smart Visuals recovery. No keyword or asset decisions live here."""
import hashlib
import json
import os
import time
import re
from pathlib import Path
from urllib.parse import urlparse

from hinglish_clean.detection import write_json

CHECK_VERSION = 2


def profile_source(url):
    parsed=urlparse(url or '')
    host=(parsed.hostname or '').casefold()
    return any(host==d or host.endswith('.'+d) for d in
        ('espncricinfo.com','cricinfo.com','ndtv.com','iplt20.com','bcci.tv','icc-cricket.com')) and bool(
        re.search(r'/(?:players?|cricketers?)/',parsed.path,re.I))


def context_key(info):
    # Paths are machine locations, not identity evidence. Include the reference's
    # bytes, so replacing a logo cannot silently reuse an earlier approval.
    spec = dict(info)
    for field in ('team_reference','identity_reference'):
        reference = spec.pop(field, None)
        if reference and Path(reference).is_file():
            spec[field+'_hash'] = hashlib.sha256(Path(reference).read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps([CHECK_VERSION, spec], sort_keys=True).encode()).hexdigest()


def checkpoint(folder, project, stage, label=''):
    project['research_state'] = {'stage': stage, 'subject': label, 'updated_at': time.time(),
        'checked_options': sum(len(s.get('options', [])) for s in project['slots']),
        'complete_banks': sum(len(s.get('options', [])) >= 5 for s in project['slots']),
        'total_banks': len(project['slots'])}
    if project.get('search_method')=='website' and project.get('review_policy')=='human':
        project['research_state']['downloaded_options']=project['research_state']['checked_options']
        project['research_state']['checked_options']=0
    write_json(Path(folder)/'visuals-project.json', project)
    marker = os.environ.get('STORYLENS_VISUALS_CHECKPOINT')
    if marker:
        file = Path(marker)
        try:
            record = json.loads(file.read_text('utf-8'))
        except (OSError, ValueError):
            record = {'projects': []}
        path = str((Path(folder)/'visuals-project.json').resolve())
        if path not in record['projects']:
            record['projects'].append(path)
        record['updated_at'] = time.time()
        write_json(file, record)


def resumable_projects(marker, root):
    try:
        paths = json.loads(Path(marker).read_text('utf-8')).get('projects', [])
    except (OSError, ValueError):
        return []
    allowed = (Path(root)/'output/visuals').resolve()
    return [p for p in map(Path, paths) if p.resolve().is_relative_to(allowed)
            and p.name == 'visuals-project.json' and p.is_file()]


def pause_project(file):
    """Leave a failed job as a usable partial review, not an endless spinner."""
    file=Path(file)
    project=json.loads(file.read_text('utf-8'))
    if 'slots' not in project:return
    project.pop('collecting',None)
    checkpoint(file.parent,project,'paused')
    from .report import write_report
    write_report(file.parent/'report.html',project)
