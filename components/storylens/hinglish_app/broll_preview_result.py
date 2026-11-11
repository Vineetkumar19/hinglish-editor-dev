"""Current B-roll preview metadata; retained stale renders are never current."""
import json
from pathlib import Path
from urllib.parse import quote


def collect(root, output):
    base = (Path(root) / 'output/broll').resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(base) or not output.is_dir():
        raise ValueError('Open a saved B-roll review from this project.')
    previews, reviews, notices = [], [], []
    for file in sorted(output.rglob('broll-project.json')):
        file = file.resolve()
        if not file.is_relative_to(output):
            continue
        project = json.loads(file.read_text('utf-8'))
        state = project.get('preview_state')
        source_url = None
        if state == 'deferred':
            notice = 'Original audio over black. Preview the options, then use Save & rebuild to create the combined preview.'
            source = (file.parent.parent / 'audio-only-source.mp4').resolve()
            if (project.get('preview_source') == '../audio-only-source.mp4'
                    and source.parent == file.parent.parent and source.is_relative_to(output)
                    and source.is_file() and source.stat().st_size > 0):
                source_url = '/broll-output/' + quote(source.relative_to(base).as_posix(), safe='/')
        elif state == 'failed':
            notice = 'Your B-roll choices are saved, but the combined preview could not finish. Open the review and retry Save & rebuild.'
        elif state not in (None, 'ready'):
            notice = 'Open the saved B-roll review to check its preview status.'
        else:
            notice = ''
        if notice and notice not in notices:
            notices.append(notice)
        reviews.append({'project': str(file), 'state': state or 'legacy', 'source_url': source_url})
    for preview in sorted(output.rglob('preview.mp4')):
        path = preview.resolve()
        if not path.is_relative_to(output) or not path.is_file():
            continue
        project_file = path.parent / 'broll-project.json'
        state = json.loads(project_file.read_text('utf-8')).get('preview_state') if project_file.is_file() else None
        if state in (None, 'ready'):
            previews.append(str(path))
    return {'previews': previews, 'broll_previews': reviews, 'broll_preview_notice': ' '.join(notices)}
