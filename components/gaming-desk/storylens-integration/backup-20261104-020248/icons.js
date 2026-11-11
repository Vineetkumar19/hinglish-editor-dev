// SVG geometry avoids font dependence and corrupted multi-byte icon characters.
(()=>{
 const paths={
 colorGrade:'<circle cx="12" cy="12" r="9"/><circle cx="8" cy="9" r="2"/><circle cx="16" cy="9" r="2"/><circle cx="12" cy="16" r="2"/>',
 reelRecreate:'<rect x="2" y="4" width="8" height="16" rx="2"/><rect x="14" y="4" width="8" height="16" rx="2"/><path d="m6 9 3 3-3 3m12-6-3 3 3 3"/>',
 templateImport:'<path d="M3 6h7l2 2h9v13H3zM12 1v12m-4-4 4 4 4-4"/>',
 templateAligner:'<path d="M3 4h18M3 20h18M5 8h5v8H5zm9 0h5v8h-5z"/>',
 templateText:'<path d="M3 5h18M12 5v15m-4 0h8M3 10h3m12 0h3"/>',
 copyPaste:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
 imageDownload:'<rect x="2" y="3" width="15" height="15" rx="2"/><path d="m2 15 5-5 5 5m6-5v12m-4-4 4 4 4-4"/>',
 nativeCaptions:'<path d="m12 2 9 5v10l-9 5-9-5V7zm0 0v10l9-5M3 7l9 5v10"/>',
 presetLibrary:'<path d="M3 3h18v18H3zM3 9h18M9 9v12"/>',
 animationPresets:'<path d="m5 4 14 8-14 8zM2 4v16"/>',
 textEffects:'<path d="M2 4h14M9 4v16m-4 0h8m5-12 1 3 3 1-3 1-1 3-1-3-3-1 3-1z"/>',
 effectsLibrary:'<path d="m12 2 2 7 7 3-7 2-2 8-3-8-7-2 7-3z"/>',
 voiceover:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
 cricketDesk:'<circle cx="12" cy="12" r="9"/><path d="M7 4c7 3 3 13 10 16M5 6c7 3 3 13 10 16"/>',
 photos:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M17 13v8m-4-4h8"/>',
 downloader:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 cinematic:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m10 8 6 4-6 4zM3 7h4m-4 10h4m10-10h4m-4 10h4"/>',
 beats:'<path d="M3 10v4m4-8v12m5-16v20m5-16v12m4-8v4"/>',
 clean:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 13 13M8 16 21 3M14 12l7-7"/>',
 script:'<path d="M4 5h16M4 12h10M4 19h16m-3-10 4 3-4 3"/>',
 captions:'<rect x="2" y="4" width="20" height="16" rx="4"/><path d="M10 9a3 3 0 1 0 0 6m9-6a3 3 0 1 0 0 6"/>',
 broll:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m10 8 6 4-6 4z"/>',
 visuals:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="8" r="2"/><path d="m3 17 5-5 5 5 3-3 5 5"/>',
 zoom:'<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M10 6v8m-4-4h8"/>',
 sound:'<path d="M4 10v4m4-8v12m4-16v20m4-16v12m4-8v4"/>',
 eyecontact:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 shorts:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="m10 8 5 4-5 4z"/>',
 aiimage:'<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/>',
 aivideo:'<rect x="2" y="5" width="15" height="14" rx="3"/><path d="m17 10 5-3v10l-5-3M7 9l5 3-5 3z"/>',
 motion:'<rect x="8" y="4" width="13" height="13" rx="2"/><path d="M4 8v12h12M2 4h3m-3 8h3"/>',
 gaming:'<path d="M7 7h10c4 0 6 12 3 13-2 1-4-4-5-4H9c-1 0-3 5-5 4C1 19 3 7 7 7zM6 10v5m-2-2h5m7-2h.1m3 3h.1"/>',
 thumbnail:'<rect x="2" y="4" width="20" height="16" rx="3"/><path d="m3 17 5-5 5 5m-1-9h7m-7 4h7"/>',
 check:'<path d="m5 12 4 4L20 5"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',
 profile:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
 play:'<path d="m8 5 11 7-11 7z"/>',pause:'<path d="M8 5v14M16 5v14"/>'};
 window.storylensIcon=(name)=>'<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(paths[name]||paths.visuals)+'</svg>';
 window.storylensEditorLogo=name=>name==='aftereffects'?'<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#00005b"/><text x="4" y="23" fill="#99f" font-family="Arial,sans-serif" font-size="21" font-weight="bold">Ae</text></svg>':name==='premiere'?'<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#00005b"/><text x="5" y="23" fill="#99f" font-family="Arial,sans-serif" font-size="22" font-weight="bold">Pr</text></svg>':name==='capcut'?'<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="white"/><path d="m6 8 20 14v3H6v-4L26 7M6 7h20v4L6 25" fill="none" stroke="#111" stroke-width="2.8" stroke-linejoin="round"/></svg>':'<svg viewBox="0 0 32 32" aria-hidden="true"><image href="/resolve-logo.png" width="32" height="32"/></svg>';
 document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.mode').forEach(b=>{const icon=b.querySelector('.mode-icon');if(icon)icon.innerHTML=window.storylensIcon(b.dataset.mode||(/beats/.test(b.href)?'sound':'broll'))});document.querySelectorAll('.result:not(.is-pending) .check').forEach(e=>e.innerHTML=window.storylensIcon('check'));const run=document.querySelector('#runIcon');if(run)run.innerHTML=window.storylensIcon('clean')});
})();
