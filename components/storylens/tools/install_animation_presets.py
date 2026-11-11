"""Install only the animation-presets route, preserving other chats' panel edits."""
from pathlib import Path
import datetime
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/animation-presets-evidence'
TARGET = Path(os.environ['APPDATA']) / 'Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js'

def patched(current):
    source = (ROOT / 'editor_plugins/shared/cep-shell.js').read_text(encoding='utf8')
    marker = "   if(host==='aftereffects'&&message.action==='animationPresets'){"
    following = "   if(host==='aftereffects'&&message.action==='presetLibrary'){"
    start = source.index(marker)
    block = source[start:source.index(following, start)]
    if marker in current:
        start = current.index(marker)
        current = current[:start] + block + current[current.index(following, start):]
    else:
        if current.count(following) != 1:
            raise RuntimeError('The panel changed. No install performed.')
        current = current.replace(following, block + following, 1)
    call = " if(host==='aftereffects')calls.animationPresets='storylensAnimationPresets';"
    if call not in current:
        anchor = " if(host==='aftereffects')calls.presetLibrary='storylensPanelPreset';"
        if current.count(anchor) != 1:
            raise RuntimeError('The action registry changed. No install performed.')
        current = current.replace(anchor, call + '\n' + anchor, 1)
    return current

if __name__ == '__main__':
    before = TARGET.read_bytes()
    result = patched(before.decode('utf8'))
    backup = OUT / 'installed-backup' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'main.js').write_bytes(before)
    config = TARGET.parent / 'config.js'
    config_before = config.read_bytes()
    if TARGET.read_bytes() != before:
        raise RuntimeError('Another chat changed the panel. No install performed.')
    TARGET.write_bytes(result.encode('utf8'))
    assert config.read_bytes() == config_before
    receipt = dict(installed=True, panel=str(TARGET), backup=str(backup),
                   sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                   config_preserved=True, native_verified=False,
                   adobe_operated=False, services_restarted=False)
    (OUT / 'installation.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps(receipt))
