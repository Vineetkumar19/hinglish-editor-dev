"""Real editing artifacts for follow-ups in the active chat only.

Only saved runner outputs/owner attachments supply paths. A model selects an ID,
never a filesystem path. Chat prose and campaign drafts are not media evidence.
"""
import hashlib
import json
from pathlib import Path
import re


def editing_requested(text):
    if re.search(r'[A-Za-z]:[\\/]',text):
        from .assistant_sources import literal_locations
        try:_,text=literal_locations(text)
        except ValueError:pass
    positive=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
    if re.match(r'^\s*(?:how|why|what|explain|is it|can i)\b',positive,re.I):return False
    # Tool-name commands are edits too. Otherwise "Run Smart Clean" skips
    # literal source resolution and silently falls back to the latest output.
    if re.search(r'\b(?:run|start|perform|execute|retry|create|make|generate|build)\s+(?:the\s+)?(?:interrupted\s+)?smart\s*(?:clean|zoom|visuals?)\b',positive,re.I):
        return True
    return bool(re.search(r'\b(?:make|create|extract|cut|turn|convert|edit|add|apply|remove)\b',positive,re.I)
        and re.search(r'\b(?:reels?|shorts?|shots|clips?|captions?|subtitles?|zoom|sound|highlights?|video|footage)\b',positive,re.I))


def catalog(assistant,snapshot):
    """Bounded current-chat catalog; survives app restarts without cross-chat recall."""
    sessions=[snapshot]
    cards=[];seen=set()
    for session in sessions:
        current=session['id']==snapshot['id']
        groups=[('latest_output',session.get('last_paths',[])),
                ('gaming_highlights',session.get('highlights_paths',[])),
                ('original_recording',session.get('original_paths',[]))]
        # A later follow-up can replace last_paths; retain older completed output
        # references from the runner's structured message, not its reply text.
        groups += [('completed_output',m['videos']) for m in reversed(session.get('messages',[]))
                   if m.get('role')=='assistant' and m.get('videos') and not m.get('error')]
        for role,paths in groups:
            paths=[str(Path(p).resolve()) for p in paths if isinstance(p,str) and
                   Path(p).suffix.lower() in {'.mp4','.mov','.mkv','.webm','.mxf','.avi'}]
            if not paths:continue
            key=tuple(paths)
            if key in seen:continue
            seen.add(key)
            highlights=set(session.get('highlights_paths',[]))
            kind='gaming_highlights' if set(paths)==highlights else role
            card={'id':hashlib.sha256(('\0'.join(paths)).encode()).hexdigest()[:16],
                  'chat_id':session['id'],'profile':session.get('profile','general'),
                  'role':kind,'current_chat':current,'latest_in_chat':role=='latest_output',
                  'names':[Path(p).name for p in paths],'paths':paths,
                  'file_count':len(paths),
                  'available':all(Path(p).is_file() for p in paths),
                  'origin_names':[Path(p).name for p in session.get('original_paths',[])],
                  'chat_title':session.get('title','')[:100]}
            cards.append(card)
            if len(cards)>=16:return cards
    return cards


def evidence(cards):
    return [{k:v for k,v in card.items() if k!='paths'} for card in cards]


def resolve(cards,source_id):
    card=next((c for c in cards if c['id']==source_id),None)
    if not card:raise ValueError('The local planner must choose a supplied saved video ID.')
    if not card['available'] or any(not Path(p).is_file() for p in card['paths']):
        raise ValueError('The referenced completed video has moved or is missing. Restore it or attach it again; no other video was substituted.')
    return list(card['paths'])
