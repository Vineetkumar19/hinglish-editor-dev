import math
from .model import Cut


def selection_limits(selections, transcripts):
    """Share padding at boundaries without sharing source frames or clipping words."""
    limits={}
    for selection in selections:
        if selection.media_id is not None:
            media=transcripts[selection.media_id].media
            limits[selection.line_index]=[0,math.floor(media.duration*float(media.rate)+1e-6)]
    for media_id,t in transcripts.items():
        ordered=sorted((s for s in selections if s.media_id==media_id),key=lambda s:s.first_word)
        fps=float(t.media.rate)
        for left,right in zip(ordered,ordered[1:]):
            a=t.words[left.last_word-1].end
            b=t.words[right.first_word].start
            minimum=math.ceil(a*fps-1e-9)
            maximum=math.floor(b*fps+1e-9)
            if minimum<=maximum:
                boundary=min(maximum,max(minimum,round((a+b)*fps/2)))
                limits[left.line_index][1]=boundary
                limits[right.line_index][0]=boundary
    return limits


def constrain_cuts(cuts,limits):
    start,end=limits
    return [Cut(c.media_id,max(start,c.start_frame),min(end,c.end_frame),c.line_index)
            for c in cuts if min(end,c.end_frame)>max(start,c.start_frame)]


def merge_ranges(ranges, gap=0):
    merged=[]
    for start,end in sorted(ranges):
        if end<=start:
            continue
        if merged and start-merged[-1][1]<=gap+1e-9:
            merged[-1]=(merged[-1][0],max(merged[-1][1],end))
        else:
            merged.append((start,end))
    return merged


def make_cuts(transcript, first, last, settings, line_index=0, conservative=False):
    words=transcript.words[first:last]
    if not words:
        return []
    low=max(0,words[0].start-settings.pre_padding)
    high=min(transcript.media.duration,words[-1].end+settings.post_padding)
    if conservative or any(not w.aligned for w in words):
        ranges=[(low,high)]
    else:
        # Union protects speech missed by either detector; never intersect away a word.
        protected=[(w.start,w.end) for w in words]
        protected += [(max(low,a),min(high,b)) for a,b in transcript.speech if a<high and b>low]
        groups=merge_ranges(protected,settings.min_silence)
        ranges=merge_ranges([(max(low,a-settings.pre_padding),min(high,b+settings.post_padding)) for a,b in groups])
    rate=float(transcript.media.rate)
    frame_limit=math.floor(transcript.media.duration*rate+1e-6)
    frames=merge_ranges([(max(0,math.floor(a*rate+1e-9)),min(frame_limit,math.ceil(b*rate-1e-9))) for a,b in ranges])
    return [Cut(transcript.media.id,int(a),int(b),line_index) for a,b in frames if b>a]
