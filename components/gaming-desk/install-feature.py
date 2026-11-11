from pathlib import Path
import datetime as dt
import json
import shutil

root = Path('D:/Full Drive/remove silence/hinglish_app/static')
output = Path(__file__).parent / 'storylens-integration'
backup = output / ('backup-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True)

def replace(name, old, new):
    p = root / name
    text = p.read_text(encoding='utf-8')
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'{name}: expected one integration anchor')
    shutil.copy2(p, backup / name)
    p.write_text(text.replace(old,new),encoding='utf-8')

replace('index.html',
    '        <button class="mode" data-mode="voiceover">',
    '        <button class="mode" data-mode="gamingDesk"><span class="mode-icon"></span><span><b>Gaming Desk</b><small>Game releases, updates &amp; memes</small></span></button>\n        <button class="mode" data-mode="voiceover">')
replace('app.js',
    '"cricketDesk": "http://127.0.0.1:8879/",',
    '"cricketDesk": "http://127.0.0.1:8879/", "gamingDesk": "http://127.0.0.1:8880/",')
replace('app.js',
    "    cricketDesk:['CRICKET DESK','Cricket Desk','','',''],",
    "    cricketDesk:['CRICKET DESK','Cricket Desk','','',''],\n    gamingDesk:['GAMING DESK','Gaming Desk','','',''],")
replace('feature-tools.js',
    "  const tools={cricketDesk:",
    "  const tools={gamingDesk:'GPT · Game news · Saved inbox',cricketDesk:")
replace('icons.js',
    " cricketDesk:",
    " gamingDesk:'<path d=\"M7 7h10c4 0 6 12 3 13-2 1-4-4-5-4H9c-1 0-3 5-5 4C1 19 3 7 7 7zM6 10v5m-2-2h5m7-2h.1m3 3h.1\"/>',\n cricketDesk:")
(output / 'installation.json').write_text(json.dumps({'installed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'feature':'Gaming Desk','entry':'Storylens > Show tools > Gaming Desk','url':'http://127.0.0.1:8765/?tool=gamingDesk','inbox':'http://127.0.0.1:8880/','backup':str(backup),'scope':'Web feature menu, native Adobe panel unchanged','browser_validation':'pending'},indent=2),encoding='utf-8')
print('Gaming Desk feature installed without restarting Storylens')
