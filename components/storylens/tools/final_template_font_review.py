"""Safe final probes. Record discovered failures without repairing them."""
import hashlib
import json
from pathlib import Path
from template_font_audit import extract_aep_fonts

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'output/template-fonts'
before = json.loads((folder / 'audit-before.json').read_text('utf-8'))
after = json.loads((folder / 'audit-after.json').read_text('utf-8'))
native = json.loads((folder / 'native-verification.json').read_text('utf-8-sig'))
installation = json.loads((folder / 'install-receipt.json').read_text('utf-8'))
findings = []
try:
    extract_aep_fonts(b'/CoolTypeFont /0 << /0 (\xfe\xff\x00)')
except Exception as e:
    findings.append({'id':'corrupt-font-table', 'confirmed':True, 'trigger':'A malformed AEP UTF-16 font literal with an odd number of bytes', 'expected':'Inventory should report that project and continue', 'actual':type(e).__name__, 'impact':'One malformed font table can stop the offline bulk inventory.', 'fixed':False})
active_missing = native['all_project_fonts']['missing']
findings.append({'id':'substitution-design-limit', 'confirmed':True, 'trigger':'Use Civil War History Slideshow with OLDSPORT02ATHLETICNCV absent', 'expected':'Exact reference typography needs the original font', 'actual':'AE displayed substitute text; font report identified the missing face and alignment succeeded.', 'impact':'Substitutes can change widths, wrapping and style; exact visual fit was not verified across all templates.', 'fixed':False})
findings.append({'id':'installed-but-substituted', 'confirmed':True, 'trigger':'Install the owner-bundled MyriadPro-Regular while 2.aep is open', 'expected':'Current project recognizes the new face', 'actual':'Windows registration succeeded but the live project retains its font substitute.', 'impact':'The open project still needs font refresh/reopen or an explicit native replacement. Owner project was not reopened or permanently rewritten.', 'fixed':False})
result = {'source_projects_unchanged':{p['path']:p['sha256'] for p in before['projects']} == {p['path']:p['sha256'] for p in after['projects']},
 'owner_project_sha256': hashlib.sha256(Path(r'D:\AE mere edited files\2.aep').read_bytes()).hexdigest(),
 'audited_projects':len(after['projects']),'font_candidates':len(after['references']),
 'prepared_faces':len(installation['fonts']),'registered_faces':sum(f.get('status')=='installed' for f in installation['fonts']),
 'offline_unresolved_candidates':after['missing_candidates'],'active_project_missing':active_missing,
 'unit_tests':{'node_passed':32,'python_passed':5,'tdd_red_observed':True},
 'live_validation':{'native_script':True,'real_template_layer':True,'once_only':True,'source_video_audio_preserved':True,'duplicate_press_rejected':True,
 'panel_visible':True,'panel_button_click':False,'button_blocker':'Windows automation identifies the CEP child as a different process; direct click was refused and its AX index unavailable. Native action was validated through File > Scripts.',
 'full_template_library_playback':False,'premiere_dynamic_link_roundtrip':False,'saved_owner_project':False},
 'final_findings':findings}
(folder/'final-review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
report=['TEMPLATE FONT STATUS — 25 OCTOBER 2026','',f"94 projects scanned; 138 font-name candidates. {result['registered_faces']} new/per-user registrations; Roboto Regular existing registration retained and activated.",
 'Sources and licenses: library/template-fonts/sources.json. Original projects unchanged.',
 '', 'CURRENT AE PROJECT — unresolved active font names:']
report += [f"- {row['name']} ({row['occurrences']} text uses)" for row in active_missing]
report += ['', 'Other unverified/offline font references (some may be unused fallback table entries):'] + ['- '+name for name in after['missing_candidates']]
report += ['', 'Future templates: Template Aliner continues with native AE temporary font substitution and lists missing names. Check fonts examines the active comp and its nested comps. No silent permanent font replacement.',
 'Exact fonts and exact layout are not guaranteed for unavailable or licensed faces. This does not repair expression errors or missing media/plugins.',
 'Unit checks passed; native script result inspected. Actual panel click, all-project native playback and Premiere roundtrip remain unverified.',
 '', 'Final review findings (left unfixed at owner instruction):']+[f"- {f['impact']}" for f in findings]
(folder/'Font Status.txt').write_text('\n'.join(report),encoding='utf-8')
print(json.dumps({'audited_projects':result['audited_projects'],'registered':result['registered_faces'],'active_missing':len(active_missing),'source_projects_unchanged':result['source_projects_unchanged'],'confirmed_final_findings':len(findings)}))
