"""Capture the active Premiere sequence and import it into Resolve, without a video render.

Premiere's Storylens panel and activated Resolve must already be open.
Use a new --folder for each handoff revision; --resume reuses the frozen capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request

if __package__:
    from .resolve_handoff import require, run, write_receipt
    from .conform_audit import audit
else:
    from resolve_handoff import require, run, write_receipt
    from conform_audit import audit

ROOT = Path(__file__).resolve().parents[2]


def capture(folder, expected_project=None, resume=False, appearance=False):
    folder.mkdir(parents=True, exist_ok=True)
    context_file = folder / 'premiere-capture.json'
    xml = folder / 'timeline.xml'
    if context_file.exists():
        require(resume, 'This handoff already has a capture. Use --resume or a new folder.')
        saved = json.loads(context_file.read_text('utf-8'))
        require(not appearance or saved.get('appearance_cache'),
                'This frozen revision has no appearance cache. Capture a new revision with appearance enabled.')
        if expected_project:
            require(Path(saved['project_id']).resolve() == Path(expected_project).resolve(),
                    'The frozen capture belongs to another Premiere project.')
        require(xml.is_file() and hashlib.sha256(xml.read_bytes()).hexdigest() == saved['xml_sha256'],
                'The frozen timeline XML changed. Preserve this handoff and create a new revision.')
        return xml, saved
    config = json.loads((ROOT / 'cache/app/bridge.json').read_text('utf-8'))

    def api(route, data=None):
        request = urllib.request.Request(config['url'] + '/api/native-tools/' + route,
            data=json.dumps(data).encode('utf-8') if data is not None else None,
            headers={'X-Hinglish-Token': config['token'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    panels = [p for p in api('connections')['connections'] if p['host'] == 'premiere']
    require(len(panels) == 1, 'Open one connected Storylens panel inside Premiere.')
    if expected_project:
        require(Path(panels[0]['project_id']).resolve() == Path(expected_project).resolve(),
                'Premiere has another project open. Select the intended edit first.')
    command_file = folder / 'capture-command.json'
    if command_file.exists():
        saved_command = json.loads(command_file.read_text('utf-8'))
        row = api('status?id=' + saved_command['id'])
    else:
        request_id = 'resolve-handoff-' + hashlib.sha256(str(folder.resolve()).encode()).hexdigest()[:32]
        payload = {'appearance_cache': True, 'capture_id':request_id.removeprefix('resolve-handoff-')} if appearance else {}
        row = api('command', {'host': 'premiere', 'action': 'context', 'payload': payload,
                              'request_id': request_id})
        write_receipt(command_file, row)
    while row['status'] in ('queued', 'sent'):
        time.sleep(1)
        row = api('status?id=' + row['id'])
        write_receipt(folder / 'capture-status.json', row)
    require(row['status'] == 'confirmed', row.get('error') or 'Premiere did not confirm the capture. Inspect it before retrying.')
    context = row['result']
    require(context['project_id'] == panels[0]['project_id'], 'Premiere changed projects during capture.')
    shutil.copy2(context['timeline_xml'], xml)
    context['xml_sha256'] = hashlib.sha256(xml.read_bytes()).hexdigest()
    write_receipt(context_file, context)
    return xml, context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--project', required=True, help='A separate Resolve destination project name')
    parser.add_argument('--expected-premiere-project', type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--compound', action='store_true')
    parser.add_argument('--preserve-appearance', action='store_true',
                        help='Ask Premiere to render a compatibility cache including its native effects; imports a flattened edit')
    parser.add_argument('--allow-incomplete-conform', action='store_true',
                        help='Import a diagnostic edit despite reported appearance gaps; never certify full appearance')
    args = parser.parse_args()
    folder = args.folder.resolve()
    xml, context = capture(folder, args.expected_premiere_project, args.resume,args.preserve_appearance)
    coverage = audit(xml, context)
    write_receipt(folder / 'appearance-audit.json', coverage)
    require(args.preserve_appearance or args.allow_incomplete_conform or not coverage['issues'],
            'The edit contains appearance that XML cannot certify. Read ' +
            str(folder / 'appearance-audit.json') +
            '. Preserve those effects through native reconstruction or rendered effect ranges before a final handoff.')
    if args.preserve_appearance:
        from cache_to_xml import wrap
        import xml.etree.ElementTree as ET
        cached=Path(context['appearance_cache']['output'])
        source_sequence=ET.parse(xml).getroot().find('sequence')
        xml=folder/'appearance-timeline.xml'
        media=wrap(cached,xml)
        require(media['frames']==int(source_sequence.findtext('duration')) and
                abs(media['fps']-context['fps'])<.001,
                'The native appearance cache duration/frame rate differs from the captured sequence.')
        source_format=source_sequence.find('media/video/format/samplecharacteristics')
        require(media['width']==int(source_format.findtext('width')) and
                media['height']==int(source_format.findtext('height')),
                'The native export preset changed the sequence dimensions. The cache is preserved for inspection.')
        coverage['resolved_by_native_appearance_cache']=True
        write_receipt(folder/'appearance-media.json',media)
    result = run(xml, args.project, folder / 'resolve-receipt.json', args.compound)
    result['intermediate_render_used']=args.preserve_appearance
    result['appearance_audit']=coverage
    write_receipt(folder/'resolve-receipt.json',result)
    print(json.dumps({'status': result['status'], 'project': result['project'],
                      'source_sequence': context['name'], 'intermediate_render_used':args.preserve_appearance}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'needs_review', 'error': str(error)}))
        sys.exit(1)
