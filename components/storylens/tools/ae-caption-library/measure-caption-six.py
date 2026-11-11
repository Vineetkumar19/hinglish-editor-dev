"""Build native Caption 6 from the inspected 1,492-frame source, without AE control.

The previous browser profile supplies traced annotation paths, not invented extra
recipes. Native timing/row bands below come from the actual source frame review.
"""
from pathlib import Path
import json, hashlib, copy
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/caption-six-ae'; DEST=ROOT/'editor_plugins/caption-six'
DEST.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
old=json.loads((ROOT/'hinglish_captions/serif_circle_reference.json').read_text(encoding='utf8'))
# The historical browser profile contains already double-encoded Portuguese
# strings. Repair that source metadata only; never transcode the owner's script.
for recipe in old['recipes']:
    if 'Ã' in recipe['text'] or 'Â' in recipe['text']:
        try: recipe['text']=recipe['text'].encode('latin1').decode('utf8')
        except (UnicodeEncodeError,UnicodeDecodeError): pass
identity=json.loads((OUT/'source.json').read_text(encoding='utf8'))
assert identity['sha256']==hashlib.sha256(Path(identity['source']).read_bytes()).hexdigest()
fonts={'sans':'StorylensCircleSans-SemiBold.ttf','serif':'PlayfairDisplay-BoldItalic.ttf','italic':'InterDisplay-SemiBoldItalic.ttf'}
metrics={}; ps={}
for role,name in fonts.items():
    path=ROOT/'hinglish_captions/fonts'/name
    with TTFont(path) as f:
        ps[role]=[f['name'].getDebugName(6)]; gs=f.getGlyphSet(); glyphs={}
        for code,g in f.getBestCmap().items():
            pen=BoundsPen(gs); gs[g].draw(pen)
            glyphs[str(code)]=[f['hmtx'][g][0],*(pen.bounds or (0,0,0,0))]
        metrics[role]={'units':f['head'].unitsPerEm,'glyphs':glyphs,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(DEST/'glyph-metrics.json').write_text(json.dumps(metrics,separators=(',',':')),encoding='utf8')

# Source states: frame boundary, exclusive end, exact text. Single states replace
# earlier words at the same position; these are not simultaneous stacked rows.
states=[(104,109,'Se ele'),(109,118,'não tem'),(118,123,'uma'),(123,133,'base'),(133,137,'para'),(137,158,'converter'),(158,170,'um'),(170,184,'dois'),(184,194,'dez'),(194,208,'vinte'),(252,268,'nunca'),(268,275,'que'),(275,284,'isso'),(284,287,'vai'),(287,294,'fazer'),(294,297,'um'),(297,303,'insta'),(303,320,'flopado'),(320,328,'virar'),(328,332,'uma'),(332,346,'máquina'),(346,366,'de vendas.'),(366,381,'Ele precisa'),(381,393,'entender'),(393,397,'que'),(397,408,'um post'),(408,418,'vai atuar'),(418,444,'muito bem'),(444,453,'pra'),(453,465,'converter'),(465,470,'uma'),(470,485,'base,'),(485,488,'ou'),(488,506,'seja,'),(560,574,'Existem'),(574,592,'exceções,'),(592,598,'como'),(623,631,'ou um'),(658,665,'e tem'),(665,677,'muita'),(677,687,'gente'),(687,698,'entrando'),(698,715,'no perfil,'),(715,720,'mas'),(720,728,'se você'),(728,741,'não explicar'),(741,749,'isso'),(749,754,'pra'),(754,762,'ele,'),(762,786,'meu amigo,'),(836,842,'Ele vai'),(842,849,'querer'),(849,866,'alterar,'),(866,875,'ele vai'),(875,882,'querer'),(882,903,'explicações'),(903,907,'do'),(907,924,'porque'),(924,933,'ele não'),(933,939,'está'),(939,964,'atraindo'),(964,967,'e'),(967,985,'vendendo'),(985,1001,'mais'),(1001,1003,'e'),(1003,1023,'no fim'),(1023,1040,'vocês'),(1040,1050,'dois'),(1050,1059,'vão se'),(1059,1071,'sentir'),(1071,1104,'frustrados'),(1104,1113,'ele'),(1167,1183,'e você'),(1225,1235,'e além'),(1235,1244,'disso,'),(1244,1252,'toda'),(1252,1267,'a jornada'),(1267,1276,'dele'),(1276,1289,'ter sido'),(1289,1296,'um'),(1296,1314,'saco.'),(1318,1321,'Então'),(1321,1328,'deixa'),(1328,1342,'claro'),(1342,1358,'a função'),(1358,1365,'do seu'),(1365,1380,'serviço.'),(1380,1388,'Se não'),(1388,1404,'fechar,'),(1404,1411,'tudo'),(1411,1418,'bem.'),(1418,1426,'Talvez'),(1426,1443,'no futuro'),(1443,1450,'você'),(1450,1457,'ainda'),(1457,1471,'tenha'),(1471,1479,'uma'),(1479,1492,'chance.')]
(OUT/'inspected-source-states.json').write_text(json.dumps({'source':identity,'visually_inspected_frames':[0,1491],'every_frame_sheets':47,'states':states,'excluded_scene_flashes':[[101,105],[556,560],[833,837],[1314,1318]],'note':'Every decoded frame inspected in consecutive frame sheets; boundary estimates are to one source frame. Shirt logo is excluded from caption masks.'},indent=2,ensure_ascii=False),encoding='utf8')

def rgb(s): return [int(s[i:i+2],16) for i in (1,3,5)]
recipes=[]
def stack(index,name,start,end,onsets,bands=None):
    r=copy.deepcopy(old['recipes'][index]); rows=[]
    for i,row in enumerate(r['rows']):
        face=row.get('face','sans')
        rows.append({'id':f'row_{i}','words':row['words'],'source_row':i,'band':(bands or [x.get('band',j) for j,x in enumerate(r['rows'])])[i], 'offset':row.get('x',360)-360,'font':face,'size':row.get('size',56),'fill_rgb':rgb(row.get('color','#FFFFFF')),'case':row.get('case','source'),'source_onset':onsets[i],'rise_frames':3 if index==0 and i==0 else 4 if index==0 and i==1 else 6,'fade_frames':2 if index==0 and i==0 else 3,'role':'main' if face=='serif' else 'support'})
    # The actual reels/que/explodiu reference is a three-row entrance, unlike
    # the older browser profile's single-row approximation.
    if index==11:
        rows=[dict(rows[0],words=[0],band=0,offset=-25),dict(rows[1],words=[1],band=1,offset=12,source_onset=639),dict(rows[1],id='row_2',source_row=2,words=[2],band=2,offset=0,source_onset=643)]
    recipes.append({'id':name,'text':r['text'],'source_start':start,'source_end':end,'motion':'rise','rows':rows,'decorations':r.get('decorations',[]),'replace_words':False})
def replace(name,entries,motion='cut',face='sans'):
    words=[]; rows=[]
    for i,(start,end,text) in enumerate(entries):
        ids=list(range(len(words),len(words)+len(text.split()))); words+=text.split()
        rows.append({'id':f'state_{i}','words':ids,'source_row':i,'band':0,'offset':0,'font':face,'size':56,'fill_rgb':[255,255,255],'case':'source','source_onset':start,'source_off':end,'role':'support'})
    recipes.append({'id':name,'text':' '.join(words),'source_start':entries[0][0],'source_end':entries[-1][1],'motion':motion,'rows':rows,'decorations':[],'replace_words':True})

stack(0,'unique_post',0,36,[1,10,14,25])
stack(1,'three_sans_rows',36,60,[37,44,52])
stack(2,'green_serif_question',60,101,[60,65,81,91])
replace('small_phrase_replacements',states[:6])
replace('count_blur_replacements',states[6:10],'count')
stack(3,'red_circle_statement',212,252,[212,226,239])
replace('plain_replacements',[s for s in states if 297<=s[0]<=346])
stack(5,'serif_inline_funnel',506,556,[506,523,526,543])
replace('brief_replacements',[s for s in states if 560<=s[0]<=592])
recipes.append({'id':'two_sans_rows','text':'tráfego pago','source_start':598,'source_end':623,'motion':'rise','replace_words':False,'decorations':[],'rows':[{'id':f'row_{i}','words':[i],'source_row':i,'band':i,'offset':0,'font':'sans','size':56,'fill_rgb':[255,255,255],'case':'source','source_onset':[598,612][i],'role':'support'} for i in range(2)]})
stack(11,'reels_three_rows',631,658,[631,639])
stack(6,'red_circle_warning',786,833,[786,786,798,818])
replace('italic_replacements',[s for s in states if s[0] in (849,882)],face='italic')
stack(7,'green_result',1113,1167,[1113,1125,1131,1148])
stack(8,'red_lost_client',1183,1225,[1183,1195,1204])
replace('closing_replacements',[s for s in states if 1380<=s[0]<=1411])

# Actual compressed-source colour samples (interior saturated glyph pixels only).
colour_samples=[]
for frame,box in [(97,(130,450,228,475)),(1145,(95,445,288,478)),(1214,(118,422,242,449))]:
    a=np.asarray(Image.open(OUT/'frames'/f'{frame:04}.jpg'))[box[1]:box[3],box[0]:box[2]].astype(int)
    mask=(a[:,:,1]>160)&(a[:,:,1]>a[:,:,0]*1.7)&(a[:,:,1]>a[:,:,2]*1.25) if frame!=1214 else (a[:,:,0]>170)&(a[:,:,0]>a[:,:,1]*2)&(a[:,:,0]>a[:,:,2]*1.6)
    samples=a[mask]; colour_samples.append({'frame':frame,'box_half':box,'pixels':len(samples),'median_rgb':np.median(samples,axis=0).astype(int).tolist() if len(samples) else None})
green=colour_samples[1]['median_rgb']; red=colour_samples[2]['median_rgb']
for r in recipes:
    for row in r['rows']:
        c=row['fill_rgb']
        if c[1]>c[0]*1.4: row['fill_rgb']=green
        elif c[0]>c[1]*2 and c[0]>100: row['fill_rgb']=red
    r['source_slot']=len([x for x in recipes[:recipes.index(r)]])

# Compare actual single-word silhouettes against bundled candidate font files.
# This is a raster fit; it cannot prove the original project's font identity.
target=np.asarray(Image.open(OUT/'frames/0310.jpg'))[406:441,124:236]
mask=(target.min(2)>155)&(target.max(2)-target.min(2)<42)
ys,xs=np.where(mask); mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
fits=[]
for name in ['Inter-SemiBold.ttf','Inter-Bold.otf','Inter-Medium.otf','InterDisplay-SemiBoldItalic.ttf']:
    best=(0,None,None)
    for size in range(45,65):
        font=ImageFont.truetype(str(ROOT/'hinglish_captions/fonts'/name),size)
        for tracking in [-60,-50,-40,-30,-20,0]:
            im=Image.new('L',(450,100)); d=ImageDraw.Draw(im); pen=10
            for ch in 'flopado': d.text((pen,5),ch,font=font,fill=255); pen+=font.getlength(ch)+size*tracking/1000
            arr=np.asarray(im)>155; y,x=np.where(arr)
            if not len(x): continue
            arr=arr[y.min():y.max()+1,x.min():x.max()+1]
            # Same physical design scale: source is half resolution.
            arr=np.asarray(Image.fromarray(arr).resize((max(1,arr.shape[1]//2),max(1,arr.shape[0]//2))))>0
            h=max(mask.shape[0],arr.shape[0]); w=max(mask.shape[1],arr.shape[1]); a=np.zeros((h,w),bool); b=a.copy()
            a[:mask.shape[0],:mask.shape[1]]=mask; b[:arr.shape[0],:arr.shape[1]]=arr
            iou=float((a&b).sum()/max(1,(a|b).sum()))
            if iou>best[0]: best=(iou,size,tracking)
    fits.append({'file':name,'iou':round(best[0],4),'size':best[1],'tracking':best[2]})

profile={'id':'caption_6_ae_v1','name':'Caption 6','folder_name':'Caption 6','public_style':'caption_6','revision':1,'reference':identity['source'].replace('\\','/'),'reference_sha256':identity['sha256'],'reference_frames':1492,'source_fps':30,'anchor_y':.63,'design_unit':'short_side','safe_width_fraction':.68,'word_gap_em':.20,'ink_gap':4,'independent_fit':True,'fonts':ps,'font_files':fonts,'tracking':{'sans':-50,'serif':-50,'italic':-50},'colours':{'white':[255,255,255],'green':green,'red':red},'recipes':recipes,'measurement_limit':'All 1,492 decoded source frames inspected. Bundled Inter SemiBold / Playfair Display Bold Italic are silhouette candidates, not certified source project fonts. Native rendering, exact optical spacing and motion fidelity require owner AE testing. Original source flash/footage/camera excluded.','background':'transparent','annotation_policy':'Only reference text-linked drawn ellipses and underlines, editable shape paths. No source scene, UI or background.','motion':{'rise_frames':7,'fade_frames':5,'travel':46,'blur':7.5,'ease_out':[0.16,1,0.3,1],'rotation':0,'camera':'none; preserve text-local entrance rather than source footage camera'},'fit_policy':'Reserve complete row slots; fit each band independently, avoid simultaneous word/row collisions, paginate long content without rewriting.'}
(DEST/'profile.json').write_text(json.dumps(profile,indent=2,ensure_ascii=False),encoding='utf8')
(OUT/'measurements.json').write_text(json.dumps({'source':identity,'colour_samples':colour_samples,'single_word_font_candidates':fits,'font_identity':'inferred, not certified','all_frames_inspected':1492,'recipes':len(recipes),'source_flash_excluded':True,'native_validation':'not run; owner testing'},indent=2),encoding='utf8')
print(json.dumps({'recipes':len(recipes),'colours':profile['colours'],'font_candidates':fits}))
