"""Isolated manual sound analysis; no automatic mix or editor import."""
import argparse
import html
import json
from pathlib import Path


def command(root,source,script,creator,lease,density):
    return ['-m','hinglish_app.panel_sound_worker','--root',str(root),'--input',str(source),
            '--script-file',str(script),'--creator-context',str(creator),
            '--resource-lease',str(lease),'--density',density]


def execute(root,source,script_file,creator_file,lease,density):
    from hinglish_sound.recommendation_pipeline import run
    from hinglish_cut.model_preferences import preferences
    root=Path(root).resolve();script=Path(script_file).read_text('utf-8-sig')
    if not script.strip():raise ValueError('Paste your shared script before requesting sound suggestions.')
    source=Path(source).resolve()
    if source.is_dir():
        supported={'.mp4','.mov','.mxf','.mkv','.avi','.mts','.m2ts','.webm','.xml'}
        files=[p.resolve() for p in source.iterdir() if p.is_file() and p.suffix.lower() in supported]
        if len(files)!=1:raise ValueError('Choose one video or captured timeline for this sound review. Your uploaded files are kept.')
        source=files[0]
    creator=json.loads(Path(creator_file).read_text('utf-8-sig'))
    selected=preferences(root)
    models={role:selected[key] for role,key in (('planning','planning_model'),('vision','vision_model'),('embedding','embedding_model')) if selected.get(key)}
    result=run(root,source,script,creator,execute_local=True,resource_lease=lease,
               expected_models=models,script_role='spoken_reference',density=density)
    if result['status'] not in ('ready','no_match'):
        raise ValueError(result.get('notice') or 'Sound suggestions could not finish. Saved analysis is kept.')
    folder=Path(result['folder']).resolve()
    if not folder.is_relative_to(root/'output/sound-recommendations') or not folder.is_dir():
        raise ValueError('The saved sound review is outside this application result.')
    page=folder/'report.html'
    notice=html.escape(result.get('notice','Review the saved sound alternatives.'))
    page.write_text('<!doctype html><meta charset="utf-8"><title>Sound suggestions · Storylens</title>'
        '<style>body{background:#171a1f;color:#edf1f6;font:16px/1.6 system-ui;max-width:800px;margin:40px auto;padding:24px}</style>'
        '<h1>Sound suggestions</h1><p>'+notice+'</p><p>Review the timed alternatives in your editor’s Storylens panel. '
        'No automatic mix or timeline placement was created.</p>',encoding='utf-8')
    return page


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','input','script-file','creator-context','resource-lease'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--density',choices=('low','medium','high'),default='medium')
    args=parser.parse_args()
    try:page=execute(args.root,args.input,args.script_file,args.creator_context,args.resource_lease,args.density)
    except (ValueError,OSError) as error:
        print('Error: '+str(error),flush=True);return 1
    print('Results: '+str(page),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
