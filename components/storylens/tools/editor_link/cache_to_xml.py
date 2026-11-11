"""Wrap an existing local media cache in an editable timeline XML (no encoding)."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def wrap(video, output):
    from hinglish_cut.media import fingerprint, probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    import av
    video=Path(video).resolve();output=Path(output).resolve()
    media=probe(video,allow_silent=True)
    # Count real decoded frames, not merely a container duration estimate.
    with av.open(str(video)) as container:
        frames=sum(1 for _ in container.decode(video=0))
    if not frames:raise ValueError('The cache has no decoded picture frames.')
    output.parent.mkdir(parents=True,exist_ok=True)
    export_xml(output,[Cut(media.id,0,frames,0)],{media.id:media})
    info={'media':str(video),'sha256':fingerprint(video),
          'frames':frames,'fps':float(media.rate),'width':media.width,'height':media.height,
          'xml':str(output),'encoded_by_this_step':False}
    output.with_suffix('.media.json').write_text(json.dumps(info,indent=2),encoding='utf8')
    return info


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--media',type=Path,required=True);p.add_argument('--xml',type=Path,required=True);a=p.parse_args()
    print(json.dumps(wrap(a.media,a.xml)))
