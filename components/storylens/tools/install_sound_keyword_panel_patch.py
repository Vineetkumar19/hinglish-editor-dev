"""Patch only keyword-bin handling in the owner's existing installed Adobe panels."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
installed=Path.home()/'AppData/Roaming/Adobe/CEP/extensions'
evidence=root/'output/sound-keyword-folder-validation'
for name,source in [('Storylens-premiere-cep','premiere-panel.jsx'),('Storylens-after-effects-cep','aftereffects-panel.jsx')]:
    target=installed/name/'jsx/panel.jsx'
    if not target.exists():
        print(name+': not installed');continue
    text=target.read_text('utf-8');original=text
    current=(root/'editor_plugins/shared'/source).read_text('utf-8')
    if source=='premiere-panel.jsx':
        if 'function storylensSoundKeywordBins(' not in text:
            helper=next(line for line in current.splitlines() if line.startswith('function storylensSoundKeywordBins('))
            text=helper+'\n'+text
        line=' if(manifest.keyword_folders)storylensSoundKeywordBins(manifest.keyword_folders);'
        if line not in text:
            anchor=next(line for line in text.splitlines() if 'var bin=app.project.rootItem.createBin' in line)
            text=text.replace(anchor,anchor+'\n'+line,1)
    else:
        line=next(line for line in current.splitlines() if 'if(manifest.keyword_folders){var soundBin=' in line)
        if line not in text:
            anchor=next(line for line in text.splitlines() if "manifest.clips.length+' separate media layers.'" in line)
            text=text.replace(anchor,line+'\n'+anchor,1)
    if text!=original:
        backup=evidence/(name+'-before.jsx')
        if not backup.exists():shutil.copy2(target,backup)
        target.write_text(text,encoding='utf-8')
    print(name+': keyword folders connected')
