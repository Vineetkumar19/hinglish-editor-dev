"""The owner's explicit SmartZoom sound selection takes priority over the general library."""
import json
from pathlib import Path

POLICY_FILE='config.zoom-sounds.local.json'


def approved(root):
    root=Path(root)
    file=root/POLICY_FILE
    if not file.is_file():
        if (root/'library/zoom-approved/whoosh').is_dir():
            raise ValueError('The approved SmartZoom sound settings are missing. Restore config.zoom-sounds.local.json before adding sounds. Your video is kept; the general library will not be substituted.')
        return None
    data=json.loads(file.read_text('utf-8'))
    assets=[]
    for item in data.get('assets',[]):
        path=Path(item['path'])
        if not path.is_absolute():path=root/path
        path=path.resolve()
        if not path.is_file():
            raise ValueError(f'An approved SmartZoom sound is missing: {path.name}. Restore it in the approved collection, then retry. Your video is kept; another library will not be substituted.')
        assets.append({**item,'path':str(path)})
    if not assets:
        raise ValueError('The approved SmartZoom sound collection is empty. Add a basic whoosh or swipe file to that collection, then retry. Your video is kept.')
    return {**data,'assets':assets}
