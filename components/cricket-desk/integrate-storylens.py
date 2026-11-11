"""Install the requested static Storylens feature without restarting its workers."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import shutil

root = Path('D:/Full Drive/remove silence/hinglish_app/static')
receipt_root = Path(__file__).parent / 'storylens-integration'
backup = receipt_root / ('backup-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True)

def replace(name, old, new):
    path = root / name
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'{name}: expected one integration anchor')
    shutil.copy2(path, backup / name)
    path.write_text(text.replace(old, new), encoding='utf-8')

replace('index.html',
    '        <button class="mode" data-mode="voiceover">',
    '        <button class="mode" data-mode="cricketDesk"><span class="mode-icon"></span><span><b>Cricket Desk</b><small>Cricket memes &amp; news inbox</small></span></button>\n        <button class="mode" data-mode="voiceover">')
replace('app.js',
    '"photos": "photos.html",',
    '"photos": "photos.html", "cricketDesk": "http://127.0.0.1:8879/",')
replace('app.js',
    "    photos:['PHOTO COLLECTOR','Photos from your screenshot','','',''],",
    "    photos:['PHOTO COLLECTOR','Photos from your screenshot','','',''],\n    cricketDesk:['CRICKET DESK','Cricket Desk','','',''],")
replace('icons.js',
    " photos:'<rect",
    " cricketDesk:'<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M7 4c7 3 3 13 10 16M5 6c7 3 3 13 10 16\"/>',\n photos:'<rect")
replace('feature-tools.js',
    "  const tools={voiceover:",
    "  const tools={cricketDesk:'GPT · Public feeds · Saved inbox',voiceover:")

page = root / 'cricket-desk.html'
if page.exists():
    shutil.copy2(page, backup / page.name)
page.write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cricket Desk · Storylens</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f8f5;color:#26382d;font:13px/1.5 "Segoe UI",system-ui,sans-serif}
nav{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 14px;background:#fff;border-bottom:1px solid #e3e7e2}
nav span{color:#66736a}nav div{display:flex;gap:12px;align-items:center}a{color:#236346;text-decoration:none}a:hover{text-decoration:underline}
button{font:inherit;border:1px solid #d7ddd6;border-radius:5px;padding:5px 10px;background:#fff;color:inherit;cursor:pointer}
iframe{display:block;width:100%;height:calc(100vh - 51px);min-height:640px;border:0;background:#f7f8f5}
details{padding:10px 14px;color:#66736a}summary{cursor:pointer}code{overflow-wrap:anywhere}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid #236346;outline-offset:3px}
@media(max-width:520px){nav{flex-wrap:wrap}nav span{font-size:12px}iframe{min-height:680px}}
</style></head><body>
<nav aria-label="Cricket Desk workspace"><span>Your saved inbox, feeds and GPT schedule</span><div><button id="reload" type="button">Reload inbox</button><a href="http://127.0.0.1:8879/" target="_blank" rel="noopener">Open full view ↗</a></div></nav>
<iframe id="inbox" src="http://127.0.0.1:8879/" title="Cricket Desk inbox"></iframe>
<details><summary>Inbox not available?</summary><p>Open <code>D:\\Workflow_Automation\\cricket-meme-inbox\\Launch Cricket Desk.vbs</code>, then choose Reload inbox. Your saved posts and research settings are kept.</p></details>
<script>document.getElementById('reload').onclick=()=>{document.getElementById('inbox').src='http://127.0.0.1:8879/'};</script>
</body></html>
''', encoding='utf-8')

files = ['index.html', 'app.js', 'icons.js', 'feature-tools.js', 'cricket-desk.html']
receipt = {
    'installed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    'feature': 'Cricket Desk',
    'entry': 'Storylens > Show tools > Cricket Desk',
    'direct_route': 'http://127.0.0.1:8765/?tool=cricketDesk',
    'inbox': 'http://127.0.0.1:8879/',
    'same_saved_database_and_schedule': True,
    'server_restart': False,
    'new_research_or_posting_job': False,
    'scope': 'Storylens web feature menu; native Adobe panels unchanged',
    'backup': str(backup),
    'sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
    'browser_validation': 'pending',
}
(receipt_root / 'result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
