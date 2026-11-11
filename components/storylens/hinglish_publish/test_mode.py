"""Owner-enabled testing permits a new upload per preparation, not per retry."""
import json
from pathlib import Path


def enabled(root, profile):
    path = Path(root) / 'config.workflow.local.json'
    data = json.loads(path.read_text('utf-8-sig')) if path.is_file() else {}
    setting = data.get('publishing_test_mode', {})
    return setting.get('allow_repeat_uploads') is True and profile in setting.get('profiles', [])
