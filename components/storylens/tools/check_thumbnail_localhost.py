"""Real local thumbnail render using the saved MI references and installed models."""
import hashlib
import json
from pathlib import Path
import time
import requests

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    from PIL import Image,ImageStat,ImageOps,ImageDraw
    assert read(Path(r'C:\Ai Models\logs\model-upgrade-completion.json'))['status']=='complete'
    assert read(ROOT/'output/validation/new-laptop/localhost-upgrade-checks.json')['passed']
    card=read(ROOT/'library/thumbnail-styles/mumbai-indians-2020/style.json')
    def originals_unchanged():
        for source in card['sources']:
            with Path(source['path']).open('rb') as stream:
                assert hashlib.file_digest(stream,'sha256').hexdigest()==source['sha256'],'A source reference changed'
    originals_unchanged()
    session=requests.Session();session.trust_env=False
    session.headers['X-Hinglish-Token']=read(ROOT/'cache/app/bridge.json')['token']
    base='http://127.0.0.1:8765'
    result=session.post(base+'/api/jobs',json={'mode':'thumbnail','profile':'cricket',
        'script':'Create three different image-led thumbnails for Mumbai Indians 2020 IPL journey. '
                 'Use the saved Mumbai reference style. They defended their title and won their fifth IPL '
                 'championship, beating Delhi Capitals by five wickets in the final. Keep supplied portraits '
                 'illustrative; do not claim they are verified photos of the 2020 final.',
        'generate_background':True,'device':'cuda'},timeout=30)
    result.raise_for_status();job=result.json();print('THUMBNAIL_JOB '+job['id'],flush=True)
    deadline=time.monotonic()+2400;previous=''
    while time.monotonic()<deadline:
        result=session.get(base+'/api/jobs/'+job['id'],timeout=30);result.raise_for_status();job=result.json()
        if job['stage']!=previous:print(job['stage'],flush=True);previous=job['stage']
        if job['status'] in ('failed','complete'):break
        time.sleep(3)
    assert job['status']=='complete',json.dumps(job,ensure_ascii=False)
    folder=Path(job['result']['folder']);project=read(folder/'thumbnail-project.json')
    assert project['profile']=='cricket' and project['reference_style']==card['id']
    assert project['ai_backgrounds'] and len(project['files'])==3
    assert len(project['generation_results'])==3 and all(row['event']=='done' for row in project['generation_results'].values())
    hashes=set();board=Image.new('RGB',(960,3*570),'#091326')
    for i,name in enumerate(project['files']):
        file=folder/name
        with file.open('rb') as stream:hashes.add(hashlib.file_digest(stream,'sha256').hexdigest())
        with Image.open(file) as picture:
            assert picture.size==(1280,720)
            board.paste(ImageOps.fit(picture.convert('RGB'),(960,540)),(0,i*570+30))
        with Image.open(folder/f'background-{i+1}.png') as background:
            assert max(ImageStat.Stat(background.convert('RGB')).var)>400,'The generated background is effectively flat'
        ImageDraw.Draw(board).text((15,i*570+8),f'{i+1}. {project["concepts"][i]["hook"]}',fill='white')
    assert len(hashes)==3
    originals_unchanged()
    board.save(folder/'three-options.jpg',quality=94)
    proof={'passed':True,'scope':'Three real local AI backgrounds plus supplied-player compositing through localhost.',
           'job_id':job['id'],'folder':str(folder),'images':job['result']['images'],
           'gallery':str(folder/'report.html'),'comparison':str(folder/'three-options.jpg'),
           'original_references_unchanged':True,'weight_fine_tuning':False,
           'learning_method':project['learning_method'],'identity_note':project['identity_note'],
           'fact_source':project['fact_source'],'visual_review_pending':True}
    (ROOT/'output/validation/new-laptop/thumbnail-upgrade-inference.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof,indent=2),flush=True)


if __name__=='__main__':main()
