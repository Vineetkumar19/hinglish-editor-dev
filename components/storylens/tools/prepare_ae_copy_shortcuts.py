"""Prepare reviewable AE-only menu commands. Never installs or changes bindings."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
folder=root/'output/copy-paste-evidence/prepared-native-shortcuts'
folder.mkdir(parents=True,exist_ok=True)
source=(root/'editor_plugins/copy-paste/menu-command.jsx').read_text('utf-8')
for name,action in [('00 Storylens Capture.jsx','copy'),('01 Storylens Paste Next.jsx','paste'),('02 Storylens Undo.jsx','undo')]:
 (folder/name).write_text(source.replace('__STORYLENS_ROOT__',root.as_posix()).replace('__STORYLENS_ACTION__',action),encoding='utf-8')
(folder/'scope.json').write_text(json.dumps({
 'status':'prepared only; no files installed and no binding changed',
 'current_bindings':{'Ctrl+1':'Tools','Ctrl+2':'Info','Ctrl+3':'Preview'},
 'proposal':'A separate backed-up AE shortcut preset, after menu commands are installed and their actual positions are verified on the next owner-controlled AE restart.',
 'not_supported':'Explorer-focused capture without a Windows-wide handler.',
 'pending':['Owner approval of AE-only binding replacement','Native menu registration after owner saves and restarts AE','Undo-safe enabled-state and Off passthrough validation','Actual AE Project focused Ctrl+1/Ctrl+2 validation'],
 'native_ctrl_c_v_save':'unchanged'},indent=2),encoding='utf-8')
