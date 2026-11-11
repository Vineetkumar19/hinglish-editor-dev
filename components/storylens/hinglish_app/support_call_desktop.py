"""Local-only bridge to the installed Cortana desktop tools."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys


CORTANA = Path('D:/Cortana')
TOPAZ = Path('D:/Editing/Editing Softwares/Topaz Video AI Pro/Topaz Video AI.exe')


def resolve_path(value, folder=False):
    from core.app_config import approved_folder_aliases, approved_search_roots
    from core.pathresolve import candidate_paths
    from tools.files import search_files, within_approved_roots, SKIP_DIRS_CASEFOLD

    roots = approved_search_roots()
    value = value.strip(' "\u201c\u201d')
    aliases = {key.casefold(): path for key, path in approved_folder_aliases().items()}
    drive = re.fullmatch(r'([a-z])(?: drive| ड्राइव)', value, re.I)
    if drive:
        value = drive[1].upper() + ':/'
    value = aliases.get(value.casefold(), value)
    names = candidate_paths(value) if Path(value).is_absolute() else [
        str(Path(root) / value) for root in roots
    ]
    matches = set()
    for name in names:
        if not within_approved_roots(name, roots):
            continue
        path = Path(name).resolve()
        if path.is_dir() or (not folder and path.is_file()):
            matches.add(path)
    if not matches and folder and not Path(value).is_absolute() and len(value) >= 3:
        from time import monotonic

        deadline = monotonic() + 4
        for root in roots:
            for directory, subfolders, _ in os.walk(root):
                if monotonic() >= deadline:
                    raise ValueError('Give the full folder path; the folder search reached its time limit.')
                path = Path(directory)
                if len(path.relative_to(root).parts) >= 4:
                    subfolders.clear()
                    continue
                subfolders[:] = [name for name in subfolders if not name.startswith('.')
                                 and name.casefold() not in SKIP_DIRS_CASEFOLD]
                for name in subfolders:
                    item = path / name
                    if name.casefold() == value.casefold() and within_approved_roots(str(item), roots):
                        matches.add(item.resolve())
                        if len(matches) > 1:
                            raise ValueError('Several folders have that name. Give the full folder path.')
    if not matches and not folder and not Path(value).is_absolute() and len(value) >= 4:
        search = search_files(query=value)
        if 'time budget' not in search.get('note', ''):
            matches = {Path(row['path']).resolve() for row in search.get('results', ())
                       if row['name'].casefold() == value.casefold()}
    if len(matches) != 1:
        raise ValueError('Give the full file or folder path so I can identify one exact item.')
    return matches.pop()


def run(request):
    from core.communication_targets import open_target
    from core.quick_commands import parse_launch
    from tools.apps import open_application
    from tools.folders import open_folder
    from tools.openpath import open_path
    from tools.web import open_website

    kind = request['kind']
    value = request['value']
    if kind == 'resolve':
        path = resolve_path(value, request.get('folder', False))
        return {'path': str(path), 'folder': path.is_dir()}
    if kind == 'path':
        path = resolve_path(value, request.get('folder', False))
        if path.is_file() and path.suffix.casefold() in {'.xlsx', '.csv', '.tsv'} and request.get('app') == 'excel':
            from core.app_config import approved_apps
            from core.processes import public_environment

            excel = approved_apps().get('excel')
            if not isinstance(excel, list) or not excel or not Path(excel[0]).is_file():
                raise ValueError('Microsoft Excel is unavailable at its configured path.')
            subprocess.Popen([*excel, str(path)], shell=False, env=public_environment())
            return {'ok': True, 'name': path.name}
        from tools.openpath import PathNotApproved
        try:
            result = open_path(str(path))
        except PathNotApproved as error:
            return {'ok': False, 'note': str(error)}
        return {'ok': bool(result.get('opened')), 'name': path.name or path.drive, 'note': result.get('note', '')}
    if kind == 'search':
        from tools.files import search_files
        results = search_files(query=value).get('results', [])
        return {'names': [row['name'] for row in results[:3]]}
    if kind == 'windows':
        from tools.computer import list_windows
        result = list_windows()
        return {'names': result.get('windows', [])[:5]}
    if kind == 'focus':
        from tools.computer import focus_window, list_windows
        matches = [title for title in list_windows()['windows'] if value.casefold() in title.casefold()]
        if len(matches) != 1:
            return {'ok': False, 'note': 'Give the exact title of one open window.'}
        result = focus_window(matches[0])
        return {'ok': bool(result.get('focused')), 'name': result.get('window', value),
                'note': result.get('note') or result.get('error', '')}
    if kind == 'draft':
        from core.desktop_drafts import draft_request
        result = draft_request('prepare', request['draft'])
        return {'ok': result.get('status') == 'draft_ready', 'note': result.get('note', ''),
                'name': request['draft']['platform']}
    if kind != 'open':
        raise ValueError('Unknown desktop action.')
    if value in ('gmail', 'whatsapp', 'instagram'):
        result = open_target(value)
        return {'ok': result.get('status') == 'opened', 'name': value, 'note': result.get('note', '')}
    if value == 'topaz video ai' and TOPAZ.is_file():
        from core.processes import public_environment

        subprocess.Popen([str(TOPAZ)], shell=False, env=public_environment())
        return {'ok': True, 'name': 'Topaz Video AI'}
    plan = parse_launch('open ' + value)
    if not plan:
        return {'ok': False, 'note': 'That app or site is not in the configured Cortana list.'}
    tool, arguments = plan
    if tool == 'open_application':
        result = open_application(**arguments)
        return {'ok': bool(result.get('launched')), 'name': result.get('app', value), 'note': result.get('note', '')}
    if tool == 'open_website' and set(arguments) == {'site'}:
        result = open_website(**arguments)
        return {'ok': bool(result.get('opened') or result.get('launched')), 'name': arguments['site']}
    if tool == 'open_folder':
        result = open_folder(**arguments)
        return {'ok': bool(result.get('opened')), 'name': arguments['name'], 'note': result.get('note', '')}
    return {'ok': False, 'note': 'Choose a configured app, website, or a local folder.'}


def main():
    sys.path[:0] = [str(CORTANA / 'agent'), str(CORTANA)]
    try:
        request = json.loads(sys.stdin.buffer.read(16384))
        result = run(request)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        result = {'ok': False, 'note': str(error)[:240]}
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
