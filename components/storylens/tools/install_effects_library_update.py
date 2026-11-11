"""Install the additive Effects bridge in the existing AE panel; never touch Adobe projects."""
from pathlib import Path
import os,json,hashlib,shutil
root=Path(__file__).resolve().parents[1]
installed=Path(os.environ['APPDATA'])/'Adobe/CEP/extensions/Storylens-after-effects-cep'
assert installed.is_dir(), 'The existing Storylens AE panel must be installed first.'
output=root/'output/effects-library-evidence'
output.mkdir(parents=True,exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
config_before=digest(installed/'js/config.js')
shell=root/'editor_plugins/shared/cep-shell.js'
data=shell.read_bytes()
assert b"message.action==='effectsLibrary'" in data
assert b"message.action==='cinematicText'" in data, 'Preserve Text bridge integration.'
target=installed/'js/main.js'
backup=output/'installed-before/js/main.js'
backup.parent.mkdir(parents=True,exist_ok=True)
if not backup.exists():shutil.copy2(target,backup)
for destination in [root/'editor_plugins/after-effects-cep/js/main.js',target,root/'output/editor-suite-20261025/after-effects-cep/js/main.js']:
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(data)
assert config_before==digest(installed/'js/config.js'), 'Shortcut/runtime configuration must remain unchanged.'
assert shell.read_bytes()==data, 'Shared shell changed concurrently; rerun the additive install with its latest version.'
receipt={'installed':str(target),'sha256':digest(target),'config_preserved':True,'backup':str(backup),'native_project_changed':False,'adobe_restarted':False,'owner_action':'Close and reopen the Storylens panel only; practical effect import/video-paste checks are pending.'}
(output/'install.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print('Effects bridge installed in the existing Storylens AE panel. Configuration preserved; Adobe was not restarted.')
