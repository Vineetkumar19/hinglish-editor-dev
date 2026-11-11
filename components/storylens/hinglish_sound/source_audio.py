"""Retain a timeline's existing stereo mix as the base when music removal is off."""
import numpy as np
from hinglish_broll.timeline import parse_xmeml
from .library import decode,SAMPLE_RATE


def original_mix(xml_path,seconds):
    timeline=parse_xmeml(xml_path)
    result=np.zeros((2,int(seconds*SAMPLE_RATE)),np.float32)
    for clip in timeline.clips:
        audio=decode(clip.path,limit=clip.source_out+.01)
        start=max(0,round(clip.start*SAMPLE_RATE))
        source=max(0,round(clip.source_in*SAMPLE_RATE))
        count=min(round((clip.source_out-clip.source_in)*SAMPLE_RATE),audio.shape[1]-source,result.shape[1]-start)
        if count>0:result[:,start:start+count]+=audio[:,source:source+count]
    return result
