"""Freeze the first reference's distinct word slots before changing its planner."""
import json
from copy import deepcopy
from pathlib import Path
from PIL import ImageFont
from hinglish_captions.renderer import _font_path


def main():
    before = Path('output/captions/kinetic-gold-reference-rebuild')
    cfg = json.loads((before/'before-reference.json').read_text('utf-8'))
    namespace = dict(__name__='hinglish_captions.kinetic_gold_before', __package__='hinglish_captions', __file__=str(before/'before-kinetic_gold.py'))
    exec((before/'before-kinetic_gold.py').read_text('utf-8'), namespace)
    namespace['profile'] = lambda: cfg
    plan = namespace['plan']
    rows = [[0,1,2,2], [0,0,1,2,2], [0]*6, [0,1], [0]+[1]*6,
            [0]+[1]*3, [0,1,0,2], [0], [0], [0], [0]*7,
            [0]*6, [0]*5, [0], [1,0], [0]*9]
    def measure(text, face, size):
        font = ImageFont.truetype(str(_font_path(face)), max(2, round(size*10)))
        box = font.getbbox(text)
        return (box[2]-box[0])/10
    for recipe, bands in zip(cfg['recipes'], rows):
        runs = plan(recipe['text'].split(), measure, False)
        for run, band in zip(runs, bands):
            run['row'] = band
            run['font'] = run.get('font', cfg['main_font'] if run['role']=='main' else cfg['support_font'])
            if recipe.get('outline_echo'):run['outline_echo'] = True
            if recipe.get('echo'):run.update(motion='cut',echo_fade_seconds=.02)
            font = ImageFont.truetype(str(_font_path(run['font'])), round(run['size']*10))
            box = font.getbbox(run['text'])
            run.setdefault('width', (box[2]-box[0])/10)
            run.setdefault('height', (box[3]-box[1])/10)
            run.pop('index', None)
            run.pop('text', None)
        recipe['runs'] = runs
    # Additional measurements from the complete chronological frame inspection.
    # Keep the old recipes too: previously saved source/slot IDs remain valid.
    for index in (10,11,12):
        for run in cfg['recipes'][index]['runs']:
            if run['role']=='support':run['font']='Inter-Bold.otf'
    cfg['recipes'][3]['text']='Sach kahun'
    cfg['recipes'][3]['runs'][1].update(x=533,width=122,height=30,typewriter=.16)
    for group in cfg['sample_groups']:
        if group['text']=='Sach kahu':group['text']='Sach kahun'
    first=deepcopy(cfg['recipes'][4]);second=cfg['recipes'][5]
    first.update(text=first['text']+' '+second['text'],stack=False,reference_compound=True)
    first['runs'][0].update(x=281,y=206.5,width=231,height=59)
    def row(words,left,right,y,size,face,band):
        widths=[measure(w,face,size) for w in words];gap=6
        scale=(right-left-gap*(len(words)-1))/sum(widths);cursor=left;result=[]
        for word,width in zip(words,widths):
            font=ImageFont.truetype(str(_font_path(face)),round(size*10));box=font.getbbox(word)
            width*=scale
            result.append(dict(x=cursor+width/2,y=y,size=size,width=width,height=(box[3]-box[1])/10,
                               font=face,row=band,role='support',motion='drop',rise=-14))
            cursor+=width+gap
        return result
    first['runs']=first['runs'][:1]+row('idea ka wait karte karte log'.split(),94,434,270,28,'arial.ttf',1)
    first['runs'][6]['delay']=.34  # Late visual entrance after the next yellow word.
    first['runs']+=[dict(second['runs'][0],x=503.5,y=279.5,width=113,height=53,row=1,motion='drop',rise=-65)]
    first['runs']+=row('nikaal dete hain'.split(),484,714,322,30,'arialbd.ttf',2)
    cfg['recipes'].append(first)
    final=cfg['recipes'][15]
    final['runs']=row('chahe tum abhi'.split(),83,270,201,30,'RobotoCondensed-Bold.ttf',0)+[
        dict(final['runs'][3],x=322,y=199,width=84,height=30,row=0,motion='drop',rise=-75)]
    final['runs']+=row('feel na'.split(),371,451,201,30,'RobotoCondensed-Bold.ttf',0)
    final['runs']+=row('kar rahe ho'.split(),461,602,225,30,'RobotoCondensed-Bold.ttf',1)
    aur=dict(text='Aur',echo=True,runs=[dict(x=368,y=207,size=75,width=124,height=62,font=cfg['main_font'],
        role='support',row=0,motion='cut',echo=True,echo_color=cfg['accent'],echo_opacity=1,echo_fade_seconds=.04)])
    cfg['recipes'].append(aur)
    # Reference annotations attach to their own complete text row. They are not
    # a full-width line under every replacement phrase.
    for index,line in [(10,[296,258,575,220,6]),(11,[317,273,587,232,8]),(12,[291,268,582,227,8])]:
        cfg['recipes'][index]['underline_path']=line
    compound=dict(text=first['text'],starts=[6,6.625,6.875,7.125,7.395833,7.645833,8.166667,8.416667,8.6875,9.083333,9.166667],end=9.270833)
    cfg['sample_groups'][4:6]=[compound]
    changes={
        'Kaafi Overthinking ke baad':([0,.291667,1.020833,1.104167],1.541667),
        'maine finally Decide kar liya':([1.5625,2.083333,2.5,2.770833,2.770833],3.145833),
        'content banana maine START kar diya':([3.166667,3.520833,4.270833,4.5,4.916667,4.916667],5.166667),
        'Sach kahun':([5.208333,5.666667],6),
        'Par Reality simple hai':([9.270833,9.895833,9.979167,10.395833],10.666667),
        'Clarity':([10.770833],11.791667),
        'Confidence':([13.625],14.625),
        'post karne ke baad Banta hai':([14.666667,14.770833,14.895833,15,15.291667,15.791667],16.145833),
        'Growth':([16.291667],16.895833),
        'consistent rehne se Milti hai':([17,17.145833,17.270833,17.604167,18.125],18.5),
        'Isliye':([18.5],19.1875),
        'Start karo':([19.229167,19.5625],20.208333),
        'chahe tum abhi Ready feel na kar rahe ho':([20.229167,20.229167,20.229167,20.625,21.145833,21.145833,21.479167,21.479167,21.479167],21.666667)}
    for group in cfg['sample_groups']:
        if group['text'] in changes:group['starts'],group['end']=changes[group['text']]
    cfg['sample_groups'].append(dict(text='Aur',starts=[16.145833],end=16.291667))
    cfg['sample_groups'].sort(key=lambda g:g['starts'][0])
    cfg.update(revision=6, status='reference_rebuild_pending_owner_review',
               notes='Measured first Klickpin reference slots. Distinct layouts and full-row reveal positions are retained on script edits. Font identity remains a visual match, not source metadata.',
               max_page_words=11,
               anchor=dict(x=.5,y=.65),
               scope='Caption typography, alignment, text annotations and motion only on plain black; no anime, stickers, illustrations or source background decorations.',
               persistence='Freeze source recipe and numeric slot across new scripts, edits, pagination, save/reopen and export. Complete-row positions are reserved before reveal.')
    encoded=json.dumps(cfg, indent=2)
    Path('hinglish_captions/kinetic_gold_reference.json').write_text(encoded, 'utf-8')
    # Lets a saved studio refresh its profile even while the local service is
    # still holding the previous presentation module in memory.
    Path('hinglish_app/static/kinetic-gold-profile.json').write_text(encoded, 'utf-8')


if __name__=='__main__':
    main()
