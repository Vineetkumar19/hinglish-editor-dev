"""Check saved Reel Recreate revisions without touching the owner's project."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from unittest.mock import patch
import json
import sys

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace))

from hinglish_app.reel_recreate import ReelRecreateService


with TemporaryDirectory(dir=workspace / 'output') as temporary:
    root = Path(temporary)
    key = 'a' * 32
    folder = root / 'output' / 'reel-recreate' / key
    folder.mkdir(parents=True)
    caption_project = root / 'output' / 'captions' / 'fixture' / 'caption-project.json'
    caption_project.parent.mkdir(parents=True)
    caption_project.write_text('{}', encoding='utf-8')
    initial = {'type': 'reel_recreate', 'version': 1, 'id': key,
               'caption': {'style': 'caption_2'}, 'caption_project': str(caption_project),
               'cues': [{'words': [{'text': 'One'}]}]}
    (folder / 'reel-plan.json').write_text(json.dumps(initial), encoding='utf-8')
    service = ReelRecreateService(root, Lock())
    with patch('hinglish_captions.project.rebuild_project', return_value={'project': {'cues': initial['cues']}}), \
         patch('hinglish_app.editor_panel.caption_manifest', side_effect=lambda project: {'style': selected[0]}):
        selected = ['caption_3']
        first = service.revise({'id': key, 'style': selected[0]})['result']
        first_id = first['revision_id']
        assert first['revision_number'] == 1
        assert (folder / 'reel-plan-revision-0001.json').is_file()
        selected[0] = 'caption_4'
        second = service.revise({'id': key, 'style': selected[0]})['result']
        assert second['revision_number'] == 2
        assert second['revision_id'] != first_id
        assert json.loads((folder / 'reel-plan-revision-0001.json').read_text('utf-8'))['revision_id'] == first_id
        assert json.loads((folder / 'reel-plan.json').read_text('utf-8'))['revision_id'] == second['revision_id']
        assert service.snapshot(key)['result']['revision_id'] == second['revision_id']
    service.pool.shutdown(wait=False)
print('Reel revision service: two distinct persisted revisions; old snapshot retained.')
