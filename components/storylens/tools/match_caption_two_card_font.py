from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
import numpy as np,json

def main():
    out=Path('tmp/caption-two-replacement-study')
    rgb=np.asarray(Image.open(out/'frame-025.jpg'))[700:750,255:470,:3]
    b=(rgb.min(2)>150)&(rgb.max(2)-rgb.min(2)<45);ys,xs=np.where(b);b=b[ys.min():ys.max()+1,xs.min():xs.max()+1];target=Image.fromarray((b*255).astype('uint8'))
    paths=[out/'Poppins-Light.ttf',out/'Urbanist.ttf',out/'Raleway.ttf',Path('C:/Windows/Fonts/GOTHIC.TTF'),Path('hinglish_captions/fonts/Inter-Variable.ttf')]
    results=[]
    for path in paths:
        with TTFont(path) as tf:axes=tf['fvar'].axes if 'fvar' in tf else []
        for weight in ([200,250,300,350,400] if axes else [0]):
            f=ImageFont.truetype(str(path),150)
            if axes:f.set_variation_by_axes([weight if a.axisTag=='wght' else a.defaultValue for a in axes])
            for tracking in [-.06,-.045,-.03,-.015,0,.015]:
                ink=Image.new('L',(1800,350));d=ImageDraw.Draw(ink);text='what to say?'
                for j,c in enumerate(text):d.text((30+f.getlength(text[:j])+j*f.size*tracking,0),c,font=f,fill=255)
                ink=ink.crop(ink.getbbox()).resize(target.size,Image.Resampling.LANCZOS);a=np.asarray(ink)>130
                score=float((a&b).sum()/max(1,(a|b).sum()));results.append((score,path.name,weight,tracking,ink))
    results.sort(key=lambda r:r[0],reverse=True);print(json.dumps([r[:4] for r in results[:10]],indent=1))
    sheet=Image.new('RGB',(1000,800),'#111');d=ImageDraw.Draw(sheet);sheet.paste(target.resize((480,65)),(0,0));d.text((500,20),'Source',fill='white')
    for i,r in enumerate(results[:9],1):sheet.paste(r[4].resize((480,65)),(0,i*75));d.text((500,i*75+20),str(r[:4]),fill='white')
    sheet.save(out/'card-font-comparison.jpg')

if __name__=='__main__':main()
