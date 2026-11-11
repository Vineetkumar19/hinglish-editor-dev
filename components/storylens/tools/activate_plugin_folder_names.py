from pathlib import Path
import hashlib,json,shutil,datetime
root=Path(__file__).resolve().parents[1]; evidence=root/'output/plugin-folder-names';evidence.mkdir(parents=True,exist_ok=True)
base=Path.home()/'AppData/Roaming/Adobe/CEP/extensions'; stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); records=[]
for panel,names in [('after-effects-cep',['jsx/photo-import.jsx','jsx/template-import.jsx','jsx/template-aliner.jsx']),('premiere-cep',['jsx/photo-import.jsx'])]:
    install=base/('Storylens-'+panel)
    if not install.is_dir():raise RuntimeError('Existing Storylens panel not found: '+panel)
    preserved={str(p.relative_to(install)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [install/'js/main.js',install/'js/config.js',install/'jsx/host.jsx'] if p.is_file()}
    for name in names:
        source=root/'editor_plugins'/panel/name;target=install/name; backup=evidence/'backups'/stamp/panel/name
        if target.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup)
        shutil.copy2(source,target)
        records.append({'panel':panel,'file':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        package=root/'output/editor-suite-20261025'/panel/name
        if package.parent.is_dir():shutil.copy2(source,package)
    for name,prior in preserved.items():
        if hashlib.sha256((install/name).read_bytes()).hexdigest()!=prior:raise RuntimeError('Concurrent panel update detected; no shared bridge was copied: '+name)
(evidence/'install.json').write_text(json.dumps({'files':records,'scope':'JSX only; no bridge/Copy Paste/config changes','archive_zip_updated':False},indent=2))
print('Installed four naming helpers. Shared panel and shortcut files preserved.')
