"""Source-only workbench navigation update. Voice Clone rename is a final step."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def replace(file,old,new):
 p=ROOT/file;s=p.read_text('utf-8')
 if new in s:return
 if s.count(old)!=1:raise RuntimeError('Unexpected source: '+file+' / '+old[:80])
 p.write_text(s.replace(old,new),encoding='utf-8')

native={'templateImport':'Import Template','templateAligner':'Template Aligner','templateText':'Template Text',
        'copyPaste':'Copy Paste','imageDownload':'Image Downloader','nativeCaptions':'3D Captions',
        'presetLibrary':'Template Library','animationPresets':'Animation Presets','textEffects':'Cinematic Text','effectsLibrary':'Effects Library'}
p=ROOT/'hinglish_app/static/index.html';s=p.read_text('utf-8')
s=s.replace('<b>Script Edit</b>','<b>Smart Edit</b>').replace('<b>Cinematic Reels</b><small>Music + performance shots</small>','<b>Cinematic Footage</b><small>Unique short shots & extras</small>')
if 'data-mode="colorGrade"' not in s:
 buttons='\n        <div class="tool-group-label">Editor tools</div>\n'
 for key,title in {'reelRecreate':'Reel Recreate','colorGrade':'Color Grade',**native}.items():
  buttons+=f'        <button class="mode" data-mode="{key}"><span class="mode-icon"></span><span><b>{title}</b></span></button>\n'
 s=s.replace('      </nav>',buttons+'      </nav>',1)
if 'id="toolSearch"' not in s:s=s.replace('<nav class="modes" aria-label="Editing modes">','<nav class="modes" aria-label="Editing modes"><input id="toolSearch" class="tool-search" type="search" placeholder="Find a tool" aria-label="Find a Storylens tool">')
s=s.replace('</head>','<link rel="stylesheet" href="workbench-shell.css?v=20261103"></head>') if 'workbench-shell.css' not in s else s
s=s.replace('app.js?v=20261029-visuals-website-1','app.js?v=20261103-workbench').replace('editor-handoff.js?v=20261023-all-results-1','editor-handoff.js?v=20261103-four-editors')
p.write_text(s,encoding='utf-8')
routes={'cinematic':'cinematic-footage.html','beats':'beats.html','downloader':'downloader.html','photos':'photos.html','voiceover':'voiceover.html','reelRecreate':'reel-recreate.html','colorGrade':'color-grade.html'}
for key in native:routes[key]='editor-panel.html?host=aftereffects&browser=1&tool='+('captions' if key=='nativeCaptions' else key)
replace('hinglish_app/static/app.js',"  const embedded=['cinematic','beats','downloader','photos','voiceover'].includes(mode), embedHost=$('#embeddedTools');",'  const routes='+repr(routes).replace("'",'"')+";\n  const embedded=Boolean(routes[mode]), embedHost=$('#embeddedTools');$('.panel').dataset.embedded=String(embedded);")
replace('hinglish_app/static/app.js',"frame.src=mode+'.html?embedded=1';", "frame.src=routes[mode]+(routes[mode].includes('?')?'&':'?')+'embedded=1';")
replace('hinglish_app/static/app.js',"embedHost.querySelectorAll('iframe').forEach(item=>item.hidden=item!==frame);", "embedHost.querySelectorAll('iframe').forEach(item=>{if(item!==frame)item.remove();});")
replace('hinglish_app/static/app.js',"  }[mode];", "  }[mode]||[mode.toUpperCase(),document.querySelector('.mode[data-mode=\"'+mode+'\"] b')?.textContent||mode,'','',''];")
p=ROOT/'hinglish_app/static/app.js';s=p.read_text('utf-8').replace('Script Edit','Smart Edit').replace("'SCRIPT EDIT'","'SMART EDIT'").replace('Cinematic Reels','Cinematic Footage').replace('CINEMATIC REELS','CINEMATIC FOOTAGE')
if "$('#toolSearch').oninput" not in s:s+="\n$('#toolSearch').oninput=()=>{const q=$('#toolSearch').value.trim().toLowerCase();$$('.mode').forEach(b=>b.hidden=!b.textContent.toLowerCase().includes(q));};\n"
p.write_text(s,encoding='utf-8')
p=ROOT/'hinglish_app/static/editor-panel.js';s=p.read_text('utf-8').replace("script:'Script Edit'","script:'Smart Edit'").replace("cinematic:'Cinematic Reels'","cinematic:'Cinematic Footage'")
s=s.replace(":mode+'.html?embedded=1&host='+host", ":(mode==='cinematic'?'cinematic-footage':mode)+'.html?embedded=1&host='+host")
p.write_text(s,encoding='utf-8')
p=ROOT/'hinglish_app/assistant_plan.py';s=p.read_text('utf-8').replace("'script': 'Script Edit'","'script': 'Smart Edit'");p.write_text(s,encoding='utf-8')
# All four destination marks, accessible names retained but no printed labels.
p=ROOT/'hinglish_app/static/editor-handoff.js';s=p.read_text('utf-8')
s=s.replace("const names={premiere:'Premiere Pro',capcut:'CapCut'};","const names={premiere:'Premiere Pro',aftereffects:'After Effects',capcut:'CapCut',resolve:'DaVinci Resolve'};")
s=re.sub(r"destinations=\(broll\|\|/.*?\)\?\{premiere:'Premiere Pro',aftereffects:'After Effects',capcut:'CapCut'\}:names",'destinations=names',s,count=1)
s=s.replace("window.storylensEditorLogo(editor)+'<span>'+destinations[editor]+'</span>'","window.storylensEditorLogo(editor)")
s=s.replace("if(broll)return window.location.assign", "if(broll&&editor!=='resolve')return window.location.assign")
p.write_text(s,encoding='utf-8')
