"""Selective reversible install of the category bridge. Never operates Adobe projects."""
from pathlib import Path
import datetime,hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/preset-library-evidence'
target=Path.home()/'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep'
installed=target/'js/main.js'
source=ROOT/'editor_plugins/shared/cep-shell.js'
before=installed.read_bytes()
current=before.decode('utf8')
prepared=source.read_text(encoding='utf8')
marker="   if(host==='aftereffects'&&message.action==='presetLibrary'){"
following="   if(host==='aftereffects'&&message.action==='effectsLibrary'){"
start=prepared.index(marker);stop=prepared.index(following,start)
block=prepared[start:stop]
if marker in current:
    start=current.index(marker);stop=current.index(following,start)
    current=current[:start]+block+current[stop:]
else:
    if current.count(following)!=1:raise RuntimeError('The existing panel changed. No install performed.')
    current=current.replace(following,block+following,1)
# Keep the legacy Text route on the same conservative native loader.
text_marker="   if(host==='aftereffects'&&message.action==='cinematicText'){"
text_end="   if(message.action==='context'){"
if text_marker in current:
    start=current.index(text_marker);stop=current.index(text_end,start)
    prepared_start=prepared.index(text_marker);prepared_stop=prepared.index(text_end,prepared_start)
    current=current[:start]+prepared[prepared_start:prepared_stop]+current[stop:]
call=" if(host==='aftereffects')calls.presetLibrary='storylensPanelPreset';"
if call not in current:
    next_call=" if(host==='aftereffects')calls.effectsLibrary="
    if current.count(next_call)!=1:raise RuntimeError('The installed action registry changed. No install performed.')
    current=current.replace(next_call,call+'\n'+next_call,1)
backup=OUT/'installed-backup'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True,exist_ok=False)
(backup/'main.js').write_bytes(before)
config=target/'js/config.js';config_before=config.read_bytes()
if installed.read_bytes()!=before:raise RuntimeError('Another chat changed the panel during preparation; no write performed.')
with installed.open('w',encoding='utf8',newline='') as f:f.write(current)
package=ROOT/'editor_plugins/after-effects-cep/js/main.js'
package.write_bytes(installed.read_bytes())
native=target/'jsx/preset-library';native.mkdir(parents=True,exist_ok=True)
for name in ['model.js','host.jsx']:
    if (native/name).exists():shutil.copy2(native/name,backup/name)
    shutil.copy2(ROOT/'editor_plugins/preset-library'/name,native/name)
# The shared source-scope helper was renamed for strict legacy parser support.
shared_source=ROOT/'editor_plugins/cinematic-text/selective.jsx'
shared_target=target/'jsx/cinematic-text/selective.jsx'
shared_target.parent.mkdir(parents=True,exist_ok=True)
if shared_target.exists():shutil.copy2(shared_target,backup/'cinematic-text-selective.jsx')
shutil.copy2(shared_source,shared_target)
shared_host=target/'jsx/cinematic-text/host.jsx'
if shared_host.exists():shutil.copy2(shared_host,backup/'cinematic-text-host.jsx')
shutil.copy2(ROOT/'editor_plugins/cinematic-text/host.jsx',shared_host)
assert config.read_bytes()==config_before
receipt={'installed':True,'panel':str(target),'backup':str(backup),'sha256':hashlib.sha256(installed.read_bytes()).hexdigest(),'config_preserved':True,'services_restarted':False,'adobe_operated':False,'owner_project_changed':False,'native_verified':False,'owner_action':'Reopen only Storylens panel to load the new bridge and repaired preview readers.'}
(OUT/'installation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps(receipt))
