"""Reversible, selective installation; no application/service restart."""
from pathlib import Path
import hashlib,datetime,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/cinematic-text-evidence';OUT.mkdir(parents=True,exist_ok=True)
target=Path.home()/'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep';installed=target/'js/main.js';source=ROOT/'editor_plugins/shared/cep-shell.js'
if not installed.is_file():raise RuntimeError('Existing Storylens AE installation is required.')
before=installed.read_bytes();text=before.decode('utf8');prepared=source.read_text('utf8')
backup=OUT/'installed-backup'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True,exist_ok=True);(backup/'main.js').write_bytes(before)
if "calls.cinematicText='storylensPanelCinematicText'" not in text:
    marker="calls.kineticTypography='storylensPanelKineticTypography';"
    if text.count(marker)!=1:raise RuntimeError('Installed bridge changed. No replacement performed.')
    text=text.replace(marker,"calls.cinematicText='storylensPanelCinematicText';"+marker,1)
    start=prepared.index("   if(host==='aftereffects'&&message.action==='cinematicText'){")
    end=prepared.index("   if(message.action==='context'){",start)
    marker="   if(message.action==='context'){"
    if text.count(marker)!=1:raise RuntimeError('Installed dispatch changed. No replacement performed.')
    text=text.replace(marker,prepared[start:end]+marker,1)
else:
    marker="   if(host==='aftereffects'&&message.action==='cinematicText'){"
    start=text.index(marker);end=text.index("   if(message.action==='context'){",start)
    source_start=prepared.index(marker);source_end=prepared.index("   if(message.action==='context'){",source_start)
    text=text[:start]+prepared[source_start:source_end]+text[end:]
if installed.read_bytes()!=before:raise RuntimeError('Another chat changed the installed panel during preparation; no write performed.')
installed.write_text(text,'utf8')
# Keep the packaged AE shell aligned without replacing its configuration/startup host.
package=ROOT/'editor_plugins/after-effects-cep/js/main.js';package.write_text(text,'utf8')
copy_source=ROOT/'editor_plugins/copy-paste/host.jsx';copy_target=target/'jsx/copy-paste.jsx'
if copy_target.is_file():shutil.copy2(copy_target,backup/'copy-paste.jsx')
shutil.copy2(copy_source,copy_target);shutil.copy2(copy_source,ROOT/'editor_plugins/after-effects-cep/jsx/copy-paste.jsx')
native=target/'jsx/cinematic-text';native.mkdir(parents=True,exist_ok=True)
for name in ['model.js','host.jsx','selective.jsx']:
    if (native/name).exists():shutil.copy2(native/name,backup/name)
    shutil.copy2(ROOT/'editor_plugins/cinematic-text'/name,native/name)
receipt={'installed':True,'panel':str(target),'backup':str(backup),'bridge_sha256':hashlib.sha256(installed.read_bytes()).hexdigest(),'copy_paste_sha256':hashlib.sha256(copy_target.read_bytes()).hexdigest(),'native_verified':False,'services_restarted':False,'owner_projects_changed':False,'fonts':'output/cinematic-text-evidence/font-install.json'}
(OUT/'installation.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))
