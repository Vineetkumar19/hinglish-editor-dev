"""Source-bound sound-family hints for the owner's imported packs.

These are search categories. A title/folder label does not prove the exact
audible source; the sound listener and owner review remain separate.
"""
import re
from pathlib import Path


def classify(relative):
    relative = Path(relative)
    parts = [part.casefold() for part in relative.parts]
    name = relative.stem.casefold()
    pack = parts[0] if parts else ''
    if pack == 'transition sound effects':
        if '-glitch-' in name:
            return 'sfx', 'glitch'
        if '-impact-' in name or '-bass-tone-' in name:
            return 'sfx', 'impact'
        if '-speed-ramp-' in name:
            return 'sfx', 'riser'
        return 'sfx', 'whoosh'
    if pack == 'w. a. production what about cinematic fx':
        section = parts[1] if len(parts) > 1 else ''
        if section in ('complex impacts', 'high impacts', 'low impacts'):
            return 'sfx', 'impact'
        if section in ('drum fills', 'risers'):
            return 'sfx', 'riser'
        if section == 'foley fx':
            return 'sfx', 'cute' if '_bells_' in name else 'impact'
        if section == 'vocal fx':
            if '_riser_' in name:
                return 'sfx', 'riser'
            return 'sfx', 'impact' if re.search(r'_one_shot(?:_|$)', name) else 'suspense'
        if section == 'white noise fx':
            if '_impact_' in name:
                return 'sfx', 'impact'
            return 'sfx', 'suspense' if '_line_' in name else 'riser'
    text = ' '.join(parts)
    rules = [('riser', r'riser|rise|build.?up|swell'),
             ('whoosh', r'whoosh|swoosh|swish|transition'),
             ('impact', r'impact|hit\b|boom|braam|slam'),
             ('suspense', r'tension|heartbeat|tick|suspense'),
             ('glitch', r'glitch|digital|stutter'),
             ('awkward', r'error|fail|scratch'),
             ('cute', r'ding|chime|sparkle|bell'),
             ('poke', r'pop|click|notification|typing'),
             ('vanish', r'vanish|poof'),
             ('retro', r'coin|game|retro'),
             ('ambience', r'drone|ambien|soundscape|atmos'),
             ('foley', r'foley|footstep|cloth|door|water|rain|bird|horse')]
    if re.search(r'\b(music|bgm|soundtracks?|songs?)\b', text) and not re.search(r'sound effects|sfx', text):
        return 'music', 'general'
    return 'sfx', next((cat for cat, pattern in rules if re.search(pattern, text)), 'general')
