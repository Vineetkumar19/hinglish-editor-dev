"""Small adapter for importing generated timelines into an open Resolve project."""
from pathlib import Path
import importlib.util
import os
import sys
import time


def _module():
    try:
        import DaVinciResolveScript as resolve_script
    except ImportError:
        resolve_script = None
    if callable(getattr(resolve_script, 'scriptapp', None)):
        return resolve_script
    locations = [
        Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) /
            'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules/DaVinciResolveScript.py',
        Path(r'C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules\DaVinciResolveScript.py')]
    for path in locations:
        if path.is_file():
            spec = importlib.util.spec_from_file_location('DaVinciResolveScript', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # The installed wrapper replaces itself with the native extension.
            resolve_script = sys.modules.get(spec.name, module)
            if callable(getattr(resolve_script, 'scriptapp', None)):
                return resolve_script
    raise RuntimeError('DaVinci Resolve scripting module was not found')


def _project():
    resolve = _module().scriptapp('Resolve')
    if not resolve:
        raise RuntimeError('Open DaVinci Resolve Studio and a project first')
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        raise RuntimeError('Open a Resolve project first')
    return resolve, project


def export_current_timeline(path):
    """Write the open Resolve timeline as FCP 7 XML (Resolve Studio scripting)."""
    resolve, project = _project()
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError('Open the timeline you want to edit in Resolve first')
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not timeline.Export(str(path), resolve.EXPORT_FCP_7_XML, resolve.EXPORT_NONE) or not path.is_file():
        raise RuntimeError('Resolve could not export the current timeline')
    return path


def import_timelines(paths, checkpoint_dir=None):
    resolve, project = _project()
    def checkpoint(label):
        if checkpoint_dir is None:return
        folder=Path(checkpoint_dir);folder.mkdir(parents=True,exist_ok=True)
        path=folder/(str(time.time_ns())+'-'+label+'.drp')
        if not resolve.GetProjectManager().ExportProject(project.GetName(),str(path)) or not path.is_file():
            raise RuntimeError('Resolve project checkpoint failed')
    checkpoint('before-cinematic-import')
    media_pool = project.GetMediaPool()
    imported = []
    for path in paths:
        timeline = media_pool.ImportTimelineFromFile(str(Path(path).resolve()))
        if not timeline:
            raise RuntimeError('Resolve could not import ' + str(path))
        imported.append(timeline.GetName())
    checkpoint('after-cinematic-import')
    return imported

