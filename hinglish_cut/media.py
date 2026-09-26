from pathlib import Path
from fractions import Fraction
import hashlib
import math
import struct
import wave
from .model import Media

SAMPLE_RATE=16000
EXTENSIONS={'.mp4','.mov','.mkv','.avi','.m4v','.webm','.mts','.m2ts'}
PREMIERE_RATE=Fraction(30)
CONFORM_VERSION='oriented-v2'


def rotation_from_display_matrix(matrix):
    """Return the counter-clockwise pixel rotation encoded by FFmpeg metadata."""
    if len(matrix)!=36:
        return 0
    values=struct.unpack('<9i',matrix)
    if values[0]==0 and values[1]==0:
        return 0
    degrees=(-math.degrees(math.atan2(values[1],values[0])))%360
    nearest=round(degrees/90)*90%360
    return nearest if abs(degrees-nearest)<1 else 0


def oriented_dimensions(width,height,rotation):
    return (height,width) if rotation in (90,270) else (width,height)


def video_rotation(path):
    """Read the first frame's display matrix from a phone recording."""
    import av
    with av.open(str(path)) as container:
        stream=container.streams.video[0]
        for frame in container.decode(stream):
            for side_data in frame.side_data:
                if str(side_data.type).endswith('DISPLAYMATRIX'):
                    return rotation_from_display_matrix(bytes(side_data))
            return 0
    return 0


def orient_frame(frame,rotation):
    """Bake a phone's display rotation into its pixel data."""
    if rotation==0:
        return frame
    import av
    import numpy as np
    pixels=frame.to_ndarray(format='rgb24')
    pixels=np.rot90(pixels,rotation//90).copy()
    return av.VideoFrame.from_ndarray(pixels,format='rgb24')


def fingerprint(path):
    """Whole-file digest prevents stale cache when footage is replaced in place."""
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(4*1024*1024):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    import av
    path=Path(path).resolve()
    with av.open(str(path)) as container:
        videos=container.streams.video
        audios=container.streams.audio
        if not videos or not audios:
            raise ValueError(f'{path.name}: both video and embedded audio are required')
        v=videos[0]; a=audios[0]
        if len(audios)>1:
            raise ValueError(f'{path.name}: multiple audio streams; create a copy with the intended audio stream first')
        fps=v.average_rate
        if not fps or fps<=0:
            raise ValueError(f'{path.name}: unknown frame rate')
        nominal=round(float(fps))
        supported=[Fraction(x) for x in (24,25,30,48,50,60)]+[Fraction(x*1000,1001) for x in (24,30,60)]
        nearest=min(supported,key=lambda x:abs(float(x-fps)))
        if abs(float(nearest-fps))>.001:
            raise ValueError(f'{path.name}: unsupported frame rate {fps}')
        fps=nearest
        if v.sample_aspect_ratio not in (None,Fraction(1)):
            raise ValueError(f'{path.name}: non-square pixels must be conformed before import')
        if int(v.metadata.get('rotate','0'))%360 or video_rotation(path):
            raise ValueError(f'{path.name}: bake camera rotation into a conformed copy first')
        times=[]
        for packet in container.demux(v):
            if packet.pts is not None:
                times.append(float(packet.pts*v.time_base))
        times.sort()
        if len(times)<2:
            raise ValueError(f'{path.name}: too few video frames')
        step=1/float(fps)
        tolerance=max(float(v.time_base)*1.1,step*.005)
        if any(abs((b-a)-step)>tolerance for a,b in zip(times,times[1:])):
            raise ValueError(f'{path.name}: variable frame rate or missing frames; conform to constant frame rate first')
        duration=len(times)/float(fps)
        return Media(hashlib.sha256(str(path).encode()).hexdigest()[:16],str(path),duration,str(fps),
                     v.width,v.height,a.codec_context.channels,a.codec_context.sample_rate,times[0])


def _encode_video_frame(output, stream, frame, frame_number):
    converted=frame.reformat(width=stream.width,height=stream.height,format='yuv420p')
    converted.pts=frame_number
    converted.time_base=Fraction(1,30)
    for packet in stream.encode(converted):
        output.mux(packet)


def conform_video(source, destination):
    """Create a 30 fps Premiere-safe working copy. The original file is never changed."""
    import av
    source=Path(source).resolve(); destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    partial=destination.with_name(destination.stem+'.partial.mp4')
    if partial.exists():
        partial.unlink()
    rotation=video_rotation(source)
    with av.open(str(source)) as input_video, av.open(str(partial),'w') as output:
        if not input_video.streams.video or not input_video.streams.audio:
            raise ValueError(f'{source.name}: both video and embedded audio are required')
        source_video=input_video.streams.video[0]
        source_audio=input_video.streams.audio[0]
        width,height=oriented_dimensions(source_video.width,source_video.height,rotation)
        video=output.add_stream('libx264',rate=30)
        video.width=width; video.height=height; video.pix_fmt='yuv420p'
        video.options={'crf':'18','preset':'medium'}
        audio=output.add_stream('aac',rate=48000)
        channels=min(max(source_audio.codec_context.channels,1),2)
        audio.layout='stereo' if channels==2 else 'mono'

        # Draw each output frame from the most recent source frame. This preserves
        # timing while turning variable-rate phone footage into a constant 30 fps file.
        previous=None; first_time=None; output_frame=0; last_time=0.0
        for frame in input_video.decode(source_video):
            if frame.pts is None:
                continue
            timestamp=float(frame.pts*frame.time_base)
            oriented=orient_frame(frame,rotation)
            if first_time is None:
                first_time=timestamp; previous=oriented; last_time=timestamp; continue
            while output_frame/30 < timestamp-first_time:
                _encode_video_frame(output,video,previous,output_frame)
                output_frame+=1
            previous=oriented; last_time=timestamp
        if previous is None:
            raise ValueError(f'{source.name}: no readable video frames')
        source_duration=(input_video.duration/av.time_base if input_video.duration else last_time-first_time+1/30)
        end_time=max(last_time-first_time+1/30,source_duration)
        while output_frame/30 < end_time:
            _encode_video_frame(output,video,previous,output_frame)
            output_frame+=1
        for packet in video.encode():
            output.mux(packet)
        # Decode audio in a fresh container. It avoids interleaving concerns while
        # preserving the original audio duration in the newly encoded MP4.
        with av.open(str(source)) as input_audio:
            source_track=input_audio.streams.audio[0]
            resampler=av.AudioResampler(format='fltp',layout=audio.layout.name,rate=48000)
            audio_position=0
            for frame in input_audio.decode(source_track):
                for converted in resampler.resample(frame):
                    converted.pts=audio_position
                    converted.time_base=Fraction(1,48000)
                    audio_position+=converted.samples
                    for packet in audio.encode(converted):
                        output.mux(packet)
            for converted in resampler.resample(None):
                converted.pts=audio_position
                converted.time_base=Fraction(1,48000)
                audio_position+=converted.samples
                for packet in audio.encode(converted):
                    output.mux(packet)
            for packet in audio.encode():
                output.mux(packet)
    partial.replace(destination)
    return probe(destination)


def prepare_media(source, conform_folder, progress=print):
    """Return source media, or a safe 30 fps working copy for phone VFR footage."""
    source=Path(source).resolve()
    try:
        return probe(source), None
    except ValueError as error:
        reason=str(error)
        if not any(marker in reason for marker in ('unsupported frame rate','variable frame rate or missing frames','bake camera rotation')):
            raise
        identity=fingerprint(source)[:20]
        working_copy=Path(conform_folder)/f'{source.stem}-{identity}-{CONFORM_VERSION}-30fps.mp4'
        if working_copy.exists():
            try:
                return probe(working_copy), f'auto_conformed_to_30fps:{source.name}'
            except ValueError:
                # The file was created by this application, so replacing its failed
                # working copy never touches the user's original recording.
                working_copy.unlink()
        progress(f'  Making a 30 fps working copy for {source.name}')
        return conform_video(source,working_copy), f'auto_conformed_to_30fps:{source.name}'


def extract_audio(media, destination):
    """Decode to disk, preserving audio offset relative to first video frame."""
    import av
    import numpy as np
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with av.open(media.path) as container, wave.open(str(destination),'wb') as out:
        stream=container.streams.audio[0]
        resampler=av.AudioResampler(format='s16',layout='mono',rate=SAMPLE_RATE)
        out.setparams((1,2,SAMPLE_RATE,0,'NONE','not compressed'))
        limit=round(media.duration*SAMPLE_RATE)
        written=0
        def write_frame(frame):
            nonlocal written
            data=frame.to_ndarray().reshape(-1).astype('<i2',copy=False)
            target=round((float(frame.pts*frame.time_base)-media.video_start)*SAMPLE_RATE) if frame.pts is not None else written
            if target>written:
                padding=min(target-written,limit-written)
                out.writeframesraw(bytes(max(0,padding)*2)); written+=padding
            overlap=max(0,written-target)
            data=data[overlap:overlap+max(0,limit-written)]
            out.writeframesraw(data.tobytes()); written+=len(data)
        for frame in container.decode(stream):
            for converted in resampler.resample(frame):
                write_frame(converted)
        for converted in resampler.resample(None):
            write_frame(converted)
        while written<limit:
            size=min(limit-written,SAMPLE_RATE*10)
            out.writeframesraw(bytes(size*2)); written+=size


def read_audio(path,start=0,end=None):
    import numpy as np
    with wave.open(str(path),'rb') as f:
        if f.getframerate()!=SAMPLE_RATE or f.getnchannels()!=1 or f.getsampwidth()!=2:
            raise ValueError('Expected 16 kHz mono PCM16 analysis audio')
        begin=min(f.getnframes(),max(0,round(start*SAMPLE_RATE)))
        stop=f.getnframes() if end is None else min(f.getnframes(),round(end*SAMPLE_RATE))
        f.setpos(begin)
        return np.frombuffer(f.readframes(max(0,stop-begin)),dtype='<i2').astype(np.float32)/32768.0


def assemble_audio(cuts,media,audio_paths,destination):
    """Reconstruct frame-quantized edits for the evaluator, with no time stretching."""
    with wave.open(str(destination),'wb') as out:
        out.setparams((1,2,SAMPLE_RATE,0,'NONE','not compressed'))
        for cut in cuts:
            m=media[cut.media_id]
            start=round(Fraction(cut.start_frame*SAMPLE_RATE)/m.rate)
            count=round(Fraction(cut.duration*SAMPLE_RATE)/m.rate)
            with wave.open(str(audio_paths[cut.media_id]),'rb') as source:
                if start+count>source.getnframes()+1:
                    raise ValueError('Cut exceeds decoded source audio')
                source.setpos(min(start,source.getnframes()))
                data=source.readframes(count)
                # At NTSC boundaries there can be one sample of rounding difference.
                out.writeframesraw(data+bytes(max(0,count*2-len(data))))
