from pathlib import Path
import shutil,hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
source=root/'editor_plugins/after-effects-cep'
installed=Path.home()/'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep'
assert installed.is_dir(), 'Existing Storylens panel is required'
relative=['js/main.js','jsx/host.jsx','jsx/template-import-model.js','jsx/template-import.jsx','jsx/template-aliner-model.js','jsx/template-aliner.jsx','jsx/copy-paste.jsx','jsx/photo-import.jsx']
backup=root/'output/template-library-import/installed-before'
backup.mkdir(parents=True,exist_ok=True)
config=hashlib.sha256((installed/'js/config.js').read_bytes()).hexdigest()
for name in relative:
    old=installed/name
    if old.exists() and not (backup/name).exists():
        (backup/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old,backup/name)
    shutil.copy2(source/name,old)
assert hashlib.sha256((installed/'js/config.js').read_bytes()).hexdigest()==config
package=root/'output/editor-suite-20261025/after-effects-cep'
shutil.copytree(source,package,dirs_exist_ok=True)
with zipfile.ZipFile(package.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in package.rglob('*'):
        if p.is_file():z.write(p,Path('after-effects-cep')/p.relative_to(package))
receipt={'installed':str(installed),'config_preserved':True,'files':{name:hashlib.sha256((installed/name).read_bytes()).hexdigest() for name in relative}}
(root/'output/template-library-import/install-receipt.json').write_text(json.dumps(receipt,indent=2))
print('Updated the existing Storylens AE panel. Shortcut configuration preserved.')
