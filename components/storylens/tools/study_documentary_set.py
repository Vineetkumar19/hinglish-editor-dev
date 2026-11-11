"""A sequential first visual pass, with labelled samples; not frame-complete analysis."""
import json
from pathlib import Path
import av
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'output/reference-analysis/crick-edit-editing-style'

def main():
    items=json.loads((FOLDER/'inventory.json').read_text(encoding='utf-8'))
    for number,item in enumerate(items,1):
        folder=FOLDER/item['slug'];folder.mkdir(exist_ok=True)
        duration=item['seconds']
        times=sorted(set([min(duration-.1,t) for t in [.5,2,5,8,12,18,25,35]]+
                         [duration*(i+.5)/24 for i in range(24)]))
        samples=[]
        with av.open(item['path']) as video:
            stream=video.streams.video[0];stream.thread_count=2
            for index,t in enumerate(times):
                video.seek(int(t/stream.time_base),stream=stream,backward=True)
                for frame in video.decode(stream):
                    actual=float(frame.pts*stream.time_base)
                    if actual+.001>=t:
                        image=frame.to_image();image.thumbnail((640,360))
                        image.save(folder/f'frame-{index:02}.jpg',quality=87)
                        samples.append({'file':f'frame-{index:02}.jpg','seconds':actual})
                        break
        for page in range(0,len(samples),16):
            canvas=Image.new('RGB',(1280,808),'#07131e');draw=ImageDraw.Draw(canvas)
            for index,sample in enumerate(samples[page:page+16]):
                image=Image.open(folder/sample['file']).convert('RGB');image.thumbnail((320,180))
                x=index%4*320;y=index//4*202;canvas.paste(image,(x+(320-image.width)//2,y))
                draw.text((x+6,y+183),f"{sample['seconds']:.2f}s",fill='white')
            canvas.save(folder/f'overview-{page//16+1:02}.jpg',quality=91)
        (folder/'samples.json').write_text(json.dumps({'source':item,'samples':samples,
           'coverage':'32 distributed visual samples including extra opening moments. Not every-frame semantic review.'},indent=2)+'\n',encoding='utf-8')
        print(f"Studied samples {number}/{len(items)}: {item['name']}",flush=True)

if __name__=='__main__':main()
