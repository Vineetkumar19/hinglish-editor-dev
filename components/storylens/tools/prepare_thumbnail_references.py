"""Build a reusable local reference pack, preserving the user's source images."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from PIL import Image,ImageChops,ImageDraw
    from hinglish_motion.assets import Remover
    source=Path(r'D:\Editing\documentry edit\final videos\final thumbnails\mi')
    target=ROOT/'library/thumbnail-styles/mumbai-indians-2020'
    target.mkdir(parents=True,exist_ok=True)
    files=[]
    for file in sorted(source.glob('*.png')):
        with file.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        files.append({'path':str(file),'sha256':digest})
    clean=source/'mi journey.png'
    with Image.open(clean) as image:
        image=image.convert('RGB');image.thumbnail((1920,1080))
        image.save(target/'reference.jpg',quality=94)
        # Exclude the old headline. Subject removal runs through the installed
        # full BiRefNet model; no identity is synthesized or weight training done.
        upper=image.crop((0,0,image.width,round(image.height*.715)))
    subjects=Remover(ROOT)(upper,'person')
    subjects.save(target/'players.png')
    # Isolate the foreground captain within the supplied collage. The neural
    # alpha supplies hair/skin edges; this polygon only excludes the other people.
    mask=Image.new('L',subjects.size)
    points=[(.405,.03),(.52,.03),(.555,.20),(.55,.32),(.59,.36),(.635,.50),
            (.68,.73),(.76,1),(.365,1),(.355,.69),(.34,.55),(.34,.44),(.37,.36),(.405,.30)]
    ImageDraw.Draw(mask).polygon([(round(x*subjects.width),round(y*subjects.height)) for x,y in points],fill=255)
    hero=subjects.copy();hero.putalpha(ImageChops.multiply(hero.getchannel('A'),mask))
    assert hero.getchannel('A').getpixel((round(.48*hero.width),round(.22*hero.height)))>200,'The captain face was clipped'
    assert hero.getchannel('A').getpixel((round(.74*hero.width),round(.20*hero.height)))==0,'Another player leaked into the portrait'
    bounds=hero.getbbox()
    if bounds:hero=hero.crop(bounds)
    hero.save(target/'captain.png')
    card={'id':'mumbai-indians-2020','match_all':['mumbai indians','2020'],'profile':'cricket',
        'learning_method':'Reference guidance and reusable subject compositing; no weight fine-tuning.',
        'rules':['Large recognizable supplied player imagery, never a text-only card.',
                 'Mumbai blue and warm gold, strong rim light and stadium depth.',
                 'Short bold English headline, large faces, clear hierarchy at mobile size.',
                 'Three different compositions; keep text away from faces.'],
        'subjects':'players.png','portrait':'captain.png','accent':'#ffd04a',
        'label':'MUMBAI INDIANS / IPL 2020',
        'hook_choices':['CHAMPIONS AGAIN','THE FIFTH TITLE','BLUE GOLD DYNASTY'],
        'verified_facts':['Mumbai Indians won IPL 2020 and their fifth IPL title.',
                          'They beat Delhi Capitals by five wickets in the final.'],
        'fact_source':'https://www.iplt20.com/news/article/dream11-ipl-2020-final-mi-vs-dc-match-report',
        'sources':files,'excluded_references':['mi journey (1).png: visible corruption/noise',
            'Untitled-4.png: exact duplicate of mi journey.png',
            'Non-MI examples inform composition only; do not mix team imagery.'],
        'identity_note':'User-supplied collage portraits are illustrative. Some reference kits are from other seasons; these are not verified photographs of the 2020 final.'}
    (target/'style.json').write_text(json.dumps(card,indent=2),encoding='utf-8')
    print(target,flush=True)


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
