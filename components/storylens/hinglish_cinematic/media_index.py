"""Content-linked media metadata and explainable bounded hybrid retrieval."""
from pathlib import Path
import math
import re
from .curation import file_hash


def display_orientation(width, height, rotation=0, sample_aspect_ratio=1):
    """Classify the picture as displayed, including phone rotation."""
    width = width * sample_aspect_ratio
    if rotation % 180:
        width, height = height, width
    if width == height:
        return 'Square'
    return 'Horizontal' if width > height else 'Vertical'


def inspect_source(path,stop=None):
    import av
    from hinglish_cut.media import video_rotation
    path=Path(path).resolve()
    content_hash=file_hash(path)
    with av.open(str(path)) as container:
        if not container.streams.video:raise ValueError('No readable video track.')
        stream=container.streams.video[0]
        stream.codec_context.thread_count=2
        pts=[];durations=[]
        for frame in container.decode(stream):
            if stop is not None and stop.is_set():raise InterruptedError('Media inspection stopped; saved analysis is kept.')
            if frame.pts is None:raise ValueError('Source has no reliable presentation timestamps.')
            pts.append(frame.pts);durations.append(frame.duration)
        if not pts:raise ValueError('No video frames.')
        timebase=str(stream.time_base)
        last_duration=durations[-1] or (pts[-1]-pts[-2] if len(pts)>1 else 1)
        capture_time=stream.metadata.get('creation_time') or container.metadata.get('creation_time')
        return {'id':content_hash,'hash':content_hash,'original_uri':str(path),'size':path.stat().st_size,
                'duration_pts':pts[-1]+last_duration-pts[0],'timebase':timebase,'origin_pts':pts[0],
                'duration':float((pts[-1]+last_duration-pts[0])*stream.time_base),
                'frame_pts':pts,'capture_time':capture_time,'time_confidence':'unverified_metadata' if capture_time else 'unknown',
                'width':stream.width,'height':stream.height,'rotation':video_rotation(path),
                'sample_aspect_ratio': str(stream.sample_aspect_ratio or 1),
                'fps':str(stream.average_rate),'variable_frame_rate':len(set(b-a for a,b in zip(pts,pts[1:])))>1,
                'color':{'range':str(stream.codec_context.color_range),'space':str(stream.codec_context.colorspace),
                         'primaries':str(stream.codec_context.color_primaries),'transfer':str(stream.codec_context.color_trc)},
                'audio_tracks':[{'index':s.index,'sample_rate':s.rate,'channels':s.codec_context.channels} for s in container.streams.audio]}


def cosine(a,b):
    if not a or len(a)!=len(b):return 0.
    if any(not math.isfinite(float(v)) for v in list(a)+list(b)):raise ValueError('Embedding values must be finite.')
    denominator=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else 0.


def normalize_search_filters(values):
    from datetime import date

    if not isinstance(values, dict):
        raise ValueError('Choose valid footage search filters.')
    filters = {}
    for key in ('phase', 'review_state', 'location', 'camera_move', 'date_from', 'date_to'):
        value = values.get(key)
        if value is None or value == '':
            continue
        if not isinstance(value, str) or len(value) > 160:
            raise ValueError(f'{key} must be short text.')
        if key in ('date_from', 'date_to'):
            value = date.fromisoformat(value).isoformat()
        filters[key] = value
    if 'date_from' in filters and 'date_to' in filters and filters['date_from'] > filters['date_to']:
        raise ValueError('The capture date range is reversed.')
    for key, maximum in (('min_duration', 3600), ('min_quality', 1), ('min_rating', 5)):
        if key not in values:
            continue
        number = float(values[key])
        if not 0 <= number <= maximum:
            raise ValueError(f'{key} is outside the supported range.')
        filters[key] = number
    return filters


def search_clips(rows,query='',filters=None,query_vector=None,embedding_model=None,limit=30):
    """Text plus same-model vector retrieval; never invent semantic embeddings."""
    filters=filters or {};terms=set(re.findall(r'\w+',query.casefold()));ranked=[]
    if not 1<=limit<=100:raise ValueError('Choose a result limit between 1 and 100.')
    if query_vector is not None and not embedding_model:raise ValueError('Identify the query embedding model.')
    for row in rows:
        if filters.get('phase') and filters['phase'] not in row.get('phase_tags',[]):continue
        if filters.get('review_state') and row.get('review_state')!=filters['review_state']:continue
        if row.get('duration',0)<filters.get('min_duration',0):continue
        if row.get('score',0)<filters.get('min_quality',0):continue
        if row.get('rating',0)<filters.get('min_rating',0):continue
        if filters.get('location') and filters['location'].casefold()!=row.get('location','').casefold():continue
        if filters.get('camera_move') and filters['camera_move'] not in row.get('camera_moves',[]):continue
        date=row.get('capture_time')
        if filters.get('date_from') and (not date or date[:10]<filters['date_from']):continue
        if filters.get('date_to') and (not date or date[:10]>filters['date_to']):continue
        text=' '.join([row.get('description',''),row.get('source',''),row.get('location',''),
                       *row.get('tags',[]),*row.get('phase_tags',[]),*row.get('camera_moves',[])])
        words=set(re.findall(r'\w+',text.casefold()));matched=sorted(words & terms)
        lexical=len(matched)/max(1,len(terms));visual=0.
        if query_vector is not None and row.get('embedding_model')==embedding_model:
            visual=max(0,cosine(query_vector,row.get('embedding',[])))
        if terms and not lexical and not visual:continue
        # With real vectors available, a single shared word must not outrank
        # strong visual evidence. Keep lexical-only searches useful without them.
        rank_score=(.15*lexical+.8*visual if query_vector is not None else .95*lexical)+.05*row.get('score',0)
        ranked.append({**row,'search_score':rank_score,
                       'match_reason':{'terms':matched,'vector_similarity':visual if query_vector is not None else None,
                                       'embedding_model':embedding_model,'uncertainty':row.get('semantic_status','needs_review')}})
    return sorted(ranked,key=lambda row:(-row['search_score'],row['id']))[:limit]
