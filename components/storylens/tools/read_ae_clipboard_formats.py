"""Read clipboard format names only after a native AE copy; never read content."""
import ctypes
import json
from pathlib import Path

user = ctypes.windll.user32
formats = []
known = {1: 'CF_TEXT', 2: 'CF_BITMAP', 8: 'CF_DIB', 13: 'CF_UNICODETEXT', 15: 'CF_HDROP'}
if not user.OpenClipboard(None):
    raise RuntimeError('Clipboard is busy; no content was read.')
try:
    current = 0
    while True:
        current = user.EnumClipboardFormats(current)
        if not current:
            break
        name = ctypes.create_unicode_buffer(256)
        found = user.GetClipboardFormatNameW(current, name, len(name))
        formats.append({'id': current, 'name': name.value if found else known.get(current, 'standard')})
finally:
    user.CloseClipboard()
result = {'source': 'Actual AE Project-panel imported photo Ctrl+C', 'formats': formats}
Path('output/copy-paste-evidence/native-project-copy-formats.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
