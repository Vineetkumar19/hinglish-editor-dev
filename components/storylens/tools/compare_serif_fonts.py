from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
out=root/'tmp/serif-font-study'
fonts=[('Instrument Serif Italic',out/'InstrumentSerif-Italic.ttf'),('DM Serif Display Italic',out/'DMSerifDisplay-Italic.ttf'),('Times New Roman Bold Italic',Path('C:/Windows/Fonts/timesbi.ttf')),('Bodoni MT Bold Italic',Path('C:/Windows/Fonts/BOD_BI.TTF')),('Bodoni MT Italic',Path('C:/Windows/Fonts/BOD_I.TTF')),('Bodoni MT Black Italic',Path('C:/Windows/Fonts/BOD_BLAI.TTF')),('Georgia Bold Italic',Path('C:/Windows/Fonts/georgiaz.ttf'))]
img=Image.new('RGB',(1100,150*(len(fonts)+1)),(18,19,21));d=ImageDraw.Draw(img)
label=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
ref=Image.open(root/'tmp/herb-reference-two/detail.jpg').crop((235,875,455,950)).resize((352,120))
img.paste(ref,(15,20));d.text((410,50),'Reference: unico (source frame at 0.8 s)',font=label,fill='white')
for i,(name,path) in enumerate(fonts,1):
    d.text((15,i*150+10),name,font=label,fill='#bbbbbb')
    f=ImageFont.truetype(str(path),100)
    d.text((15,i*150+40),'único post',font=f,fill='white',anchor='lt')
    d.text((560,i*150+40),'venda mais?',font=f,fill='#58f69d',anchor='lt')
img.save(out/'comparison.jpg')
print(out/'comparison.jpg')
