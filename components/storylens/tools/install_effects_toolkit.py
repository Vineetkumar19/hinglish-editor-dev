"""Install only the named toolkit dispatcher, preserving every other CEP route."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/effects-toolkit-evidence'
TARGET = Path.home() / 'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js'
PACKAGE = ROOT / 'editor_plugins/after-effects-cep/js/main.js'
MARKER = "    if(['toolkitCatalog','toolkitApply'].includes(payload.action)){"
ANCHOR = "    const path=require('path'),root=window.HINGLISH_APP_ROOT;if(!root)throw Error('Reopen the installed Storylens panel to use Presets.');\n"

def patched(current):
    if current.count(ANCHOR) != 1:
        raise RuntimeError('The Presets bridge changed. No install performed.')
    source = (ROOT / 'editor_plugins/shared/cep-shell.js').read_text(encoding='utf8')
    lines = [line for line in source.splitlines() if line.startswith(MARKER)]
    if len(lines) != 1:
        raise RuntimeError('Expected exactly one toolkit route.')
    block = lines[0] + '\n'
    if MARKER in current:
        existing = current.splitlines(keepends=True)
        if sum(line.startswith(MARKER) for line in existing) != 1:
            raise RuntimeError('Ambiguous toolkit route. No install performed.')
        return ''.join(block if line.startswith(MARKER) else line for line in existing)
    return current.replace(ANCHOR, ANCHOR + block, 1)

def install():
    targets = [TARGET, PACKAGE]
    original = {p: p.read_bytes() for p in targets}
    prepared = {p: patched(b.decode('utf8').replace('\r\n', '\n')).encode('utf8') for p, b in original.items()}
    backup = OUT / 'installed-backup' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    for p, data in original.items():
        (backup / ('installed-main.js' if p == TARGET else 'package-main.js')).write_bytes(data)
    config = TARGET.parent / 'config.js'
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    for p in targets:
        if p.read_bytes() != original[p]:
            raise RuntimeError('Another task changed the panel. No install performed.')
    written = []
    try:
        for p in targets:
            p.write_bytes(prepared[p])
            written.append(p)
            if p.read_bytes() != prepared[p]:
                raise RuntimeError('Installed file verification failed.')
        if hashlib.sha256(config.read_bytes()).hexdigest() != config_hash:
            raise RuntimeError('Panel config changed during install.')
    except Exception:
        for p in written:
            if p.read_bytes() == prepared[p]:
                p.write_bytes(original[p])
        raise
    receipt = {'installed': True, 'backup': str(backup), 'panel': str(TARGET),
               'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
               'config_preserved': True, 'native_verified': False,
               'adobe_operated': False, 'services_restarted': False}
    (OUT / 'installation.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps(receipt))

if __name__ == '__main__':
    install()
