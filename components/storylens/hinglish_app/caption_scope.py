"""Distinguish a truncated composition from an unrelated narration script."""
import math
from .caption_speech_text import caption_tokens
from .caption_native_match import reconcile
from .template_text_model import align_script

def scope_problem(script,observed,capture,normalizer):
    tokens=caption_tokens(script)
    if len(tokens)<8 or len(capture.get('clips',[]))!=1:return None
    matched=[w for w in reconcile(' '.join(t['spoken'] for t in tokens),observed,normalizer,align_script) if w.get('alignment')!='context-corrected']
    if len(matched)<6:return None
    span=matched[-1]['script_index']-matched[0]['script_index']+1
    if span>len(tokens)*.8 or len(matched)/span<.7:return None
    clip=capture['clips'][0];duration=capture.get('duration',0)
    if clip.get('end',0)<duration-.1:return None
    source_duration=clip.get('source_duration')
    if source_duration is None:
        try:
            import av
            with av.open(clip['path']) as media:source_duration=media.duration/av.time_base if media.duration else None
        except (OSError,ValueError,KeyError):return None
    if isinstance(source_duration,bool) or not isinstance(source_duration,(float,int)) or not math.isfinite(source_duration):return None
    available=clip.get('start',0)+source_duration-clip.get('source_in',0)
    if available<=duration+.5:return None
    return ('This composition ends at '+format(duration,'.1f')+' seconds, but its narration continues to '+format(available,'.1f')+' seconds. Only that portion was read. Use the full video length or the script for this portion; your complete script and saved speech analysis are kept.')
