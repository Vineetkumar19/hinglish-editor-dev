"""Install only the quick-motion branch inside Presets. Does not operate Adobe."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/quick-motion-evidence'
TARGET = Path.home() / 'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js'
PACKAGE = ROOT / 'editor_plugins/after-effects-cep/js/main.js'
MARKER = "    if(['motionCatalog','applyMotion'].includes(payload.action)){"
ANCHOR = "    const path=require('path'),root=window.HINGLISH_APP_ROOT;if(!root)throw Error('Reopen the installed Storylens panel to use Presets.');\n"

def route_block():
    source = (ROOT / 'editor_plugins/shared/cep-shell.js').read_text(encoding='utf8')
    return next(line + '\n' for line in source.splitlines() if line.startswith(MARKER))

def patched(current):
    if current.count(ANCHOR) != 1:
        raise RuntimeError('The Presets bridge changed. No install performed.')
    if MARKER in current:
        lines = current.splitlines(keepends=True)
        if sum(line.startswith(MARKER) for line in lines) != 1:
            raise RuntimeError('Ambiguous motion route. No install performed.')
        return ''.join(route_block() if line.startswith(MARKER) else line for line in lines)
    return current.replace(ANCHOR, ANCHOR + route_block(), 1)

def install():
    targets = [TARGET, PACKAGE]
    old = {p: p.read_bytes() for p in targets}
    prepared = {p: patched(data.decode('utf8').replace('\r\n', '\n')) for p, data in old.items()}
    backup = OUT / 'installed-backup' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    for p, data in old.items():
        (backup / ('installed-main.js' if p == TARGET else 'package-main.js')).write_bytes(data)
    config = TARGET.parent / 'config.js'
    config_bytes = config.read_bytes()
    for p, data in old.items():
        if p.read_bytes() != data:
            raise RuntimeError('Another chat changed the panel. No install performed.')
    for p in targets:
        p.write_bytes(prepared[p].encode('utf8'))
    assert config.read_bytes() == config_bytes
    receipt = dict(installed=True, panel=str(TARGET), backup=str(backup),
                   sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                   config_preserved=True, native_verified=False,
                   adobe_operated=False, services_restarted=False,
                   scope='Only motionCatalog/applyMotion branch; native files hot-loaded from workspace')
    (OUT / 'installation.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps(receipt))

if __name__ == '__main__':
    install()
