"""Create native frame evidence from the owner's replacement Caption 2 source."""
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw
from imageio_ffmpeg import get_ffmpeg_exe

SOURCE=Path('D:/Full Drive/Styles/Videos/Caption 02 - Lime Keyword Zoom.mp4')
FOLDER=Path('tmp/caption-two-replacement-study')

def main():
    FOLDER.mkdir(parents=True,exist_ok=True)
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-i',str(SOURCE),'-vf','fps=2','-q:v','2',str(FOLDER/'frame-%03d.jpg')],check=True)
    frames=list(sorted(FOLDER.glob('frame-*.jpg')))
    sheet=Image.new('RGB',(6*240,6*450),'#222222');pen=ImageDraw.Draw(sheet)
    for i,path in enumerate(frames):
        im=Image.open(path);im.thumbnail((240,420));x=i%6*240;y=i//6*450
        sheet.paste(im,(x,y+25));pen.text((x+8,y+7),f'{i*.5:.2f}s',fill='white')
    sheet.save(FOLDER/'contact.jpg')
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-i',str(SOURCE),'-vn','-ar','16000','-ac','1',str(FOLDER/'audio.wav')],check=True)
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-i',str(SOURCE),'-t','3.2','-vf','fps=30','-q:v','2',str(FOLDER/'native-%03d.jpg')],check=True)
    detail=Image.new('RGB',(6*360,5*230),'#222');pen=ImageDraw.Draw(detail)
    for i,n in enumerate(range(0,90,3)):
        im=Image.open(FOLDER/f'native-{n+1:03d}.jpg').crop((0,570,720,970)).resize((360,200));x=i%6*360;y=i//6*230
        detail.paste(im,(x,y+25));pen.text((x+8,y+5),f'{n/30:.3f}s',fill='white')
    detail.save(FOLDER/'entrances.jpg')
    print(FOLDER/'contact.jpg')

if __name__=='__main__':main()
