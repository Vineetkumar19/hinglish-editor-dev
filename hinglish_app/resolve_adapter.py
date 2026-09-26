"""Small adapter for importing generated timelines into an open Resolve project."""
from pathlib import Path
import importlib.util
import os
import sys


def _module():
    try:
        import DaVinciResolveScript as resolve_script
        return resolve_script
    except ImportError:
        locations = [
            Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) /
                'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules/DaVinciResolveScript.py',
            Path(r'C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules\DaVinciResolveScript.py')]
        for path in locations:
            if path.exists():
                spec = importlib.util.spec_from_file_location('DaVinciResolveScript', path)
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
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
        raise RuntimeError('Open the timeline you want B-roll for in Resolve first')
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not timeline.Export(str(path), resolve.EXPORT_FCP_7_XML, resolve.EXPORT_NONE) or not path.is_file():
        raise RuntimeError('Resolve could not export the current timeline')
    return path


def import_timelines(paths):
    resolve, project = _project()
    media_pool = project.GetMediaPool()
    imported = []
    for path in paths:
        timeline = media_pool.ImportTimelineFromFile(str(Path(path).resolve()))
        if not timeline:
            raise RuntimeError('Resolve could not import ' + str(path))
        imported.append(timeline.GetName())
    return imported

