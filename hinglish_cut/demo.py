from pathlib import Path
from fractions import Fraction


def create_demo_media(path,seconds=6,frequency=440,color=(26,60,80)):
    """Synthetic test media. Tones are not speech; never used to claim ASR quality."""
    import av
    import numpy as np
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with av.open(str(path),'w') as out:
        video=out.add_stream('mpeg4',rate=25)
        video.width=320; video.height=180; video.pix_fmt='yuv420p'
        audio=out.add_stream('aac',rate=48000)
        audio.layout='stereo'
        samples=np.arange(int(seconds*48000),dtype=np.float32)
        signal=.12*np.sin(2*np.pi*frequency*samples/48000)
        signal[(samples/48000%3)>1.8]=0
        vi=0; ai=0
        while vi<round(seconds*25) or ai<len(signal):
            if vi<round(seconds*25) and (vi/25<=ai/48000 or ai>=len(signal)):
                pixels=np.empty((180,320,3),dtype=np.uint8); pixels[:]=color
                pixels[:,(vi*3)%300:(vi*3)%300+20]=[230,190,100]
                frame=av.VideoFrame.from_ndarray(pixels,format='rgb24')
                frame.pts=vi; frame.time_base=Fraction(1,25)
                for packet in video.encode(frame): out.mux(packet)
                vi+=1
            else:
                chunk=signal[ai:ai+1024]
                frame=av.AudioFrame.from_ndarray(np.stack((chunk,chunk)),format='fltp',layout='stereo')
                frame.sample_rate=48000; frame.pts=ai; frame.time_base=Fraction(1,48000)
                for packet in audio.encode(frame): out.mux(packet)
                ai+=len(chunk)
        for packet in video.encode(): out.mux(packet)
        for packet in audio.encode(): out.mux(packet)
