from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np,json

def main():
    out=Path('tmp/caption-two-replacement-study');rgb=np.asarray(Image.open(out/'native-076.jpg'))[635:730,40:680,:3]
    b=(rgb[:,:,0]>170)&(rgb[:,:,1]>220)&(rgb[:,:,2]<150);ys,xs=np.where(b);b=b[ys.min():ys.max()+1,xs.min():xs.max()+1];target=Image.fromarray((b*255).astype('uint8'))
    paths=[Path('hinglish_captions/fonts')/n for n in ('Inter-Bold.otf','Inter-Variable.ttf','Inter-SemiBold.ttf','Roboto-Black.ttf')]+[Path('C:/Windows/Fonts/arialbd.ttf')]
    results=[]
    for path in paths:
        for weight in ([600,650,700,750,800,850,900] if 'Variable' in path.name else [0]):
            f=ImageFont.truetype(str(path),150)
            if weight:f.set_variation_by_axes([32,weight])
            for tracking in [-.08,-.065,-.05,-.035,-.02,0]:
                ink=Image.new('L',(2200,350));d=ImageDraw.Draw(ink);text='Understand'
                for j,c in enumerate(text):d.text((30+f.getlength(text[:j])+j*f.size*tracking,0),c,font=f,fill=255)
                ink=ink.crop(ink.getbbox()).resize(target.size,Image.Resampling.LANCZOS);a=np.asarray(ink)>150
                results.append((float((a&b).sum()/max(1,(a|b).sum())),path.name,weight,tracking,ink))
    results.sort(key=lambda r:r[0],reverse=True);print(json.dumps([r[:4] for r in results[:10]],indent=1))
    sheet=Image.new('RGB',(1200,800),'#111');d=ImageDraw.Draw(sheet);sheet.paste(target.resize((720,90)),(0,0));d.text((750,30),'Source',fill='white')
    for i,r in enumerate(results[:6],1):sheet.paste(r[4].resize((720,90)),(0,i*110));d.text((750,i*110+30),str(r[:4]),fill='white')
    sheet.save(out/'main-font-comparison.jpg')

if __name__=='__main__':main()
