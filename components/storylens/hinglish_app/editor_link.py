"""Prepare and open local handoffs between the four supported editors."""
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request
import uuid

from tools.editor_link import cache_to_xml, conform_audit, from_capcut, resolve_handoff, send_to_resolve, to_after_effects, to_capcut

from . import capcut_adapter, resolve_adapter


EDITORS = {
    'premiere': 'Premiere Pro',
    'aftereffects': 'After Effects',
    'resolve': 'DaVinci Resolve',
    'capcut': 'CapCut',
}
MEDIA = {'.mp4', '.mov', '.mxf', '.avi', '.m4v', '.mkv', '.webm'}
OPEN_LOCK = threading.Lock()
EDITOR_PROCESSES = {'premiere': 'adobe premiere pro.exe', 'aftereffects': 'afterfx.exe',
                    'resolve': 'resolve.exe', 'capcut': 'capcut.exe'}


def _path(value):
    name = str(value or '').strip().strip('"')
    path = Path(name)
    if not path.is_absolute() or name.startswith(('\\', '//')):
        raise ValueError('Paste the full path to a local file or saved CapCut draft folder.')
    return path.resolve()


def _base(root):
    return (Path(root) / 'output' / 'editor-handoffs').resolve()


def _job(root, key):
    if not re.fullmatch(r'[a-f0-9]{32}', str(key)):
        raise ValueError('Choose a prepared editor handoff first.')
    folder = _base(root) / key
    return folder, json.loads((folder / 'handoff.json').read_text('utf-8'))


def capcut_drafts(root):
    base = capcut_adapter.settings(root)[1]
    drafts = base / 'root_meta_info.json'
    if not drafts.is_file():
        return {'drafts': []}
    index = json.loads(drafts.read_text('utf-8-sig'))
    rows = []
    for item in index.get('all_draft_store', []):
        name, folder = item.get('draft_name'), item.get('draft_fold_path')
        if not name or not folder or item.get('draft_is_invisible'):
            continue
        path = Path(folder)
        if (path / 'draft_content.json').is_file():
            rows.append({'name': name, 'path': str(path)})
    return {'drafts': rows}


def _bridge(root, route, payload=None):
    cfg = json.loads((Path(root) / 'cache/app/bridge.json').read_text('utf-8'))
    req = urllib.request.Request(
        cfg['url'] + '/api/native-tools/' + route,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'X-Hinglish-Token': cfg['token'], 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    except OSError as error:
        raise ValueError('Open Storylens in Premiere Pro and check its connection. The transfer files are kept.') from error


def _rendered_path(path):
    if path.suffix.lower() not in MEDIA or not path.is_file():
        raise ValueError('Choose an existing video file from the source editor, such as MP4 or MOV.')
    return path


def _require_editor_space(target):
    import psutil
    processes = {(p.info.get('name') or '').lower() for p in psutil.process_iter(['name'])}
    other = [EDITORS[key] for key, name in EDITOR_PROCESSES.items() if key != target and name in processes]
    if other:
        raise ValueError('Save and close ' + ', '.join(other) + ' before starting ' + EDITORS[target] + '.')


def _adobe_executable(name):
    choices = sorted(Path('C:/Program Files/Adobe').glob('Adobe After Effects*/Support Files/' + name), reverse=True)
    if not choices:
        raise ValueError('Open an installed copy of After Effects, or choose a video already rendered from it.')
    return choices[0]


def _render_ae(folder, project, composition):
    if not project.is_file() or project.suffix.lower() != '.aep' or not composition.strip():
        raise ValueError('Choose a saved After Effects .aep file and enter the exact composition name.')
    _require_editor_space('aftereffects')
    media = folder / 'after-effects-render.mp4'
    with (folder / 'aerender.log').open('wb') as log:
        result = subprocess.run([str(_adobe_executable('aerender.exe')), '-project', str(project),
            '-comp', composition.strip(), '-OMtemplate', 'H.264 - Match Render Settings - 15 Mbps',
            '-output', str(media), '-mfr', 'OFF', '100', '-mem_usage', '20', '45',
            '-close', 'DO_NOT_SAVE_CHANGES'], stdout=log, stderr=subprocess.STDOUT,
            timeout=1800, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or not media.is_file():
        raise ValueError('After Effects could not render this composition. Check its name and missing media, then review ' + str(folder/'aerender.log') + '.')
    return media


def prepare(root, payload):
    source, target = payload.get('source'), payload.get('target')
    kind = payload.get('kind')
    from_result = source == 'storylens' and kind == 'media'
    if (source not in EDITORS and not from_result) or target not in EDITORS or source == target:
        raise ValueError('Choose two different editors.')
    if kind not in ('media', 'xml', 'capcut-draft', 'active', 'ae-render'):
        raise ValueError('Choose a video, timeline XML, saved CapCut draft, or active timeline.')
    if kind == 'ae-render' and source != 'aftereffects':
        raise ValueError('Choose After Effects as the source of the saved composition.')
    if kind == 'active' and source not in ('premiere', 'resolve'):
        raise ValueError('Choose a saved CapCut draft or a video for this source editor.')
    if kind == 'capcut-draft' and source != 'capcut':
        raise ValueError('Select CapCut as the source of the saved draft.')
    key = uuid.uuid4().hex
    folder = _base(root) / key
    folder.mkdir(parents=True)
    title = 'Storylens ' + (EDITORS[source]+' to ' if not from_result else '') + EDITORS[target] + ' ' + key[:8]
    timeline = folder / 'timeline.xml'
    media = None
    if kind == 'media':
        media = _rendered_path(_path(payload.get('path')))
        if from_result and not media.is_relative_to((Path(root)/'output').resolve()):
            raise ValueError('Choose a finished Storylens clip.')
        cache_to_xml.wrap(media, timeline)
    elif kind == 'ae-render':
        if not OPEN_LOCK.acquire(blocking=False):
            raise ValueError('Wait for the previous editor action to finish.')
        try:
            media = _render_ae(folder, _path(payload.get('path')), str(payload.get('composition') or ''))
            cache_to_xml.wrap(media, timeline)
        finally:
            OPEN_LOCK.release()
    elif kind == 'xml':
        source_xml = _path(payload.get('path'))
        if source_xml.suffix.lower() != '.xml' or not source_xml.is_file():
            raise ValueError('Choose an existing Final Cut Pro 7 timeline XML file.')
        timeline.write_bytes(source_xml.read_bytes())
    elif kind == 'capcut-draft':
        draft = _path(payload.get('path'))
        if draft.name.lower() == 'draft_content.json':
            draft = draft.parent
        if not (draft / 'draft_content.json').is_file():
            raise ValueError('Choose the saved CapCut draft folder containing draft_content.json.')
        try:
            from_capcut.export(draft, timeline)
        except ValueError as error:
            raise ValueError(str(error).rstrip('.') + '. Choose Video / rendered edit for a CapCut export with its effects.') from error
    elif source == 'resolve':
        resolve_adapter.export_current_timeline(timeline)
    else:
        xml, context = send_to_resolve.capture(folder)
        issues = conform_audit.audit(xml, context)['issues']
        if issues:
            raise ValueError('This Premiere sequence has effects the editable transfer cannot carry. Choose Video / rendered edit to keep its appearance.')

    return package_timeline(folder,key,source,target,kind,title,media)


def package_timeline(folder,key,source,target,kind,title,media=None):
    timeline = folder/'timeline.xml'
    try:
        resolve_handoff.inspect_xml(timeline)
    except RuntimeError as error:
        raise ValueError(str(error)) from error
    if target == 'aftereffects':
        artifact = to_after_effects.prepare(timeline, folder, title, managed_prefix=folder.parent)['script']
        instruction = 'Use an empty After Effects project or an earlier Storylens handoff. Choose Open in After Effects, or run the prepared file through File → Scripts → Run Script File.'
    elif target == 'capcut':
        artifact = to_capcut.build(timeline, folder, title, embedded_audio=media is not None)['folder']
        instruction = 'Save and close CapCut, then choose Add to CapCut Home. Reopen CapCut and select the new project.'
    elif target == 'premiere':
        artifact = str(timeline)
        instruction = 'Use File → Import in Premiere Pro, or open Storylens in the intended Premiere project and choose Import into Premiere.'
    else:
        artifact = str(timeline)
        instruction = 'Open Resolve Studio, then choose Import into Resolve. The transfer creates a separate project.'
    result = {'id': key, 'source': source, 'target': target, 'title': title,
              'kind': kind, 'artifact': artifact, 'instruction': instruction, 'status': 'prepared',
              'media': str(media) if media else ''}
    resolve_handoff.write_receipt(folder / 'handoff.json', result)
    return result


def apply(root, key):
    folder, job = _job(root, key)
    target = job['target']
    if not OPEN_LOCK.acquire(blocking=False):
        raise ValueError('Wait for the previous editor action to finish. Your prepared files are kept.')
    try:
        if target == 'capcut':
            to_capcut.register_draft(folder)
            return {'message': 'Added to CapCut Home. Reopen CapCut and select ' + job['title'] + '.'}
        if target == 'resolve':
            _require_editor_space(target)
            try:
                result = resolve_handoff.run(folder / 'timeline.xml', job['title'], folder / 'resolve-receipt.json',
                                             source_label=EDITORS.get(job['source'],'Storylens'))
            except RuntimeError as error:
                raise ValueError(str(error)) from error
            return {'message': 'Resolve saved the imported timeline in ' + result['project'] + '.'}
        if target == 'aftereffects':
            intro_receipt = folder/'intro-precomps.tsv'
            if job['kind'] == 'intro' and intro_receipt.is_file():
                rows = intro_receipt.read_text('utf-8-sig').splitlines()
                if rows and len(rows[0].split('\t')) == 7:
                    return {'message':'After Effects opened the editable intro pre-comps.'}
                raise ValueError(rows[0] if rows else 'After Effects did not confirm the intro import.')
            receipt = folder / 'ae-native-receipt.json'
            if receipt.is_file():
                result = json.loads(receipt.read_text('utf-8'))
                if result.get('status') == 'native_editable_composition_saved':
                    return {'message': 'After Effects saved the composition.', 'project': result['project']}
                raise ValueError(result.get('error') or 'Open After Effects and check the prepared script.')
            launch_receipt = folder / 'ae-launch.json'
            if launch_receipt.is_file():
                import psutil
                launch = json.loads(launch_receipt.read_text('utf-8'))
                running = any((p.info.get('name') or '').lower() in ('afterfx.exe','afterfx.com')
                              for p in psutil.process_iter(['name']))
                if running or time.time()-launch.get('started_at',0)<15:
                    return {'message':'Waiting for After Effects to confirm the import…','pending':True}
                if launch.get('transport') == 'console':
                    raise ValueError('After Effects exited before confirming the import. Open After Effects and run the prepared JSX from File → Scripts.')

            _require_editor_space(target)
            executable = _adobe_executable('AfterFX.exe')
            console = executable.with_suffix('.com')
            launcher = console if console.is_file() else executable
            with (folder/'ae-launch.log').open('ab') as log:
                process = subprocess.Popen([str(launcher), '-r', job['artifact']], stdout=log, stderr=log,
                                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            resolve_handoff.write_receipt(launch_receipt, {'pid': process.pid, 'started_at':time.time(),
                                                           'transport':'console' if launcher==console else 'gui'})
            return {'message':'After Effects is opening the composition…','pending':True}
        return import_into_premiere(root,'editor-handoff-'+job['id'],[job['artifact']],
                                    job['title'],folder/'premiere-command.json')
    finally:
        OPEN_LOCK.release()


def import_into_premiere(root, request_id, paths, title, command_path):
    if command_path.is_file():
        saved = json.loads(command_path.read_text('utf-8'))
        row = _bridge(root, 'status?id=' + saved['id'])
    else:
        panels = [p for p in _bridge(root, 'connections')['connections']
                  if p.get('host') == 'premiere' and p.get('project_id')]
        if len(panels) != 1:
            raise ValueError('Open one Storylens panel in the intended Premiere project before importing. The XML is kept.')
        row = _bridge(root, 'command', {
            'host': 'premiere', 'action': 'import', 'request_id': request_id,
            'payload': {'paths': paths, 'name': title, 'activate': True,
                        'expected': {'project_id': panels[0]['project_id']}},
        })
        resolve_handoff.write_receipt(command_path, row)
    if row['status'] == 'confirmed':
        return {'message': 'Premiere confirmed the timeline import.'}
    if row['status'] in ('queued', 'sent'):
        return {'message':'Premiere is importing the timeline…','pending':True}
    raise ValueError(row.get('error') or 'Premiere did not confirm the import. Check the receiving project before preparing another transfer.')
