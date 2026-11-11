"""Resolve owner-named files in owner-supplied folders before recalling old outputs."""
from pathlib import Path
import re

MEDIA={'.mp4','.mkv','.mov','.webm','.mxf','.avi'}


def literal_locations(text):
    # A directory may contain spaces. Prefer the longest existing prefix of the
    # literal Windows path, ending before the following natural-language clause.
    targets=[];name_text=list(text)
    for match in re.finditer(r'[A-Za-z]:[\\/][^\r\n"<>|]*',text):
        raw=match[0].strip()
        candidates=[raw.rstrip(' ,;.')]+[raw[:m.start()].rstrip(' ,;.') for m in reversed(list(re.finditer(r'[\s,;]+',raw)))]
        literal=next((p for p in candidates if Path(p).exists() and
            (not raw[len(p):].strip() or re.match(r'^(?:as|and|then|to|take|use|extract|create|make|upload|post|schedule|publish|for|with|add|choose|select|pick|from|on|using)\b|^[,;.]',raw[len(p):].strip(),re.I))),None)
        if literal is None:raise ValueError('The supplied video or folder was not found. Saved outputs will not replace that source.')
        targets.append(Path(literal).resolve())
        # Names may appear before OR after a supplied path. Mask only its
        # actual literal, preserving an inline instruction after that path.
        # Directory components are not references to videos inside them.
        name_text[match.start():match.start()+len(literal)]=' '*len(literal)
    return list(dict.fromkeys(targets)),''.join(name_text)


def named_sources(text,known=()):
    selected=[]
    targets,names=literal_locations(text)
    # An explicit filename-prefix filter authorizes a batch, not a request to
    # choose one unrelated finished video. Clip meaning/order stays with the
    # existing local Script Edit/Smart Clean engines.
    from .assistant_publish_intent import positive
    prefix_match=re.search(
        r'\b(?:use|select|include|take|pick)\s+(?:only\s+)?(?:the\s+)?'
        r'(?:raw\s+)?(?:video\s+)?files\s+whose\s+(?:file\s*names?|names?)\s+'
        r'(?:start|begin)s?\s+with\s+[\"\x27`]?([A-Za-z0-9_-]+)',positive(names),re.I)
    for target in targets:
        if target.is_file() and target.suffix.lower() in MEDIA:selected.append(target);continue
        if not target.is_dir():continue
        files=[p.resolve() for p in target.iterdir() if p.is_file() and p.suffix.lower() in MEDIA
               and p.resolve().is_relative_to(target)]
        if prefix_match:
            matches=sorted((p for p in files if p.name.casefold().startswith(prefix_match[1].casefold())),
                           key=lambda p:p.name.casefold())
            if not matches:
                raise ValueError('No video filenames start with the requested prefix in that folder. Check the prefix or folder; no other videos were selected.')
            selected.extend(matches)
            continue
        named=[p for p in files if re.search(r'(?<!\w)'+re.escape(p.stem).replace(r'\ ',r'\s+')+r'(?!\w)',names,re.I)]
        if len(named)>1:raise ValueError('More than one video matches that name in the supplied folder. Choose one of those files.')
        if named:selected.extend(named)
        elif len(files)==1:selected.extend(files)
        elif re.search(r'\b(?:choose|select|pick)\b',text,re.I):continue  # campaign planner chooses from this supplied folder
        elif files:raise ValueError('That folder has multiple videos and none matches the requested name. Name one file; old outputs will not be substituted.')
        else:raise ValueError('No supported video was found in the supplied folder.')
    if not selected and not targets:
        # Reuse an owner-supplied file by its exact name on later turns, even
        # after restart. The model cannot introduce a new filesystem path.
        matches={Path(p).resolve() for p in known if Path(p).is_file() and Path(p).suffix.lower() in MEDIA
            and re.search(r'(?<!\w)'+re.escape(Path(p).stem).replace(r'\ ',r'\s+')+r'(?!\w)',text,re.I)}
        if len(matches)>1:raise ValueError('That video name matches more than one saved source. Specify its folder.')
        selected.extend(matches)
    return list(dict.fromkeys(selected))
