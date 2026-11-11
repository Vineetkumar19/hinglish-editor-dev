"""Collect real media for one moment and PROVE each file is about the right entity.

A Gandhi story must show Gandhi only: a file is kept when it comes from the entity's own Wikidata item /
Wikipedia article, or when its title, description or Commons categories name the entity (full name or a
known alias - "Indira Gandhi" does not pass for Mahatma Gandhi)."""
import re

from .web import Media, generic_reference_allowed, generic_source_matches

LOGO_WORDS = ('logo', 'wordmark', 'icon', 'emblem', 'logotype')
# Files that name a person but usually do not show the moment a viewer expects.
WEAK_WORDS = ('signature', 'autograph', 'stamp', 'coin', 'banknote', 'coat of arms', 'seal', 'grave', 'tomb',
              'plaque', 'poster', 'book cover', 'letter', 'manuscript', 'document', 'newspaper', 'page',
              'scan', 'map', 'flag', 'graffiti', 'cartoon', 'caricature', 'drawing', 'statue', 'bust', 'memorial',
              'museum', 'postcard', 'sticker', 'audio', 'lecture', 'speech recording')
STOCK_LICENSES = {'pexels': 'Pexels License', 'pixabay': 'Pixabay Content License'}


def _norm(text):
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[\W_]+', ' ', str(text).casefold())).strip() + ' '


def mentions(text, names):
    haystack = _norm(text)
    return any(len(n) > 4 and n in haystack for n in (_norm(name) for name in names))


def proof_names(entity):
    """Names that identify the entity on their own. For people a lone surname or title that is part of
    the full name ("Gandhi", "Mahatma") is ambiguous, so it does not count; "Bapu" or "Gandhiji" do."""
    names = entity.names()
    if entity.kind != 'person':
        return names
    label_words = set(_norm(entity.label or entity.name).split())
    return [n for n in names if len(_norm(n).split()) > 1 or _norm(n).strip() not in label_words]


def locked(media, entity, *, reference_method=None):
    """True when the file is provably about this entity."""
    if generic_reference_allowed(reference_method, entity.kind, 'photo', entity.label or entity.name):
        return generic_source_matches(reference_method, f'{media.title} {media.text}')
    return media.official or mentions(f'{media.title} {media.text}', proof_names(entity))


def matches_event(media, moment, entity):
    """An event's date/stage must be present in source evidence, not merely in our search query."""
    if entity.kind != 'event':
        return True
    requested = ' '.join([entity.name, moment.visual, *moment.queries])
    evidence = f'{media.title} {media.text}'
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', requested))
    if years and not years.issubset(set(re.findall(r'\b(?:19|20)\d{2}\b', evidence))):
        return False
    if re.search(r'\bfinal\b', requested, re.I) and not re.search(r'(?<!semi[ -])\bfinal\b', evidence, re.I):
        return False
    return True


def relevance(media, moment, entity):
    """Share of the moment's own idea words (beyond the entity name) found in the file's text."""
    name_words = set(_norm(' '.join(entity.names())).split())
    wanted = {w for q in moment.queries + [moment.visual] for w in _norm(q).split()
              if len(w) > 3 and w not in name_words}
    if not wanted:
        return 0.0
    have = set(_norm(f'{media.title} {media.text}').split())
    return len(wanted & have) / len(wanted)


def score(media, moment, entity):
    text = _norm(f'{media.title} {media.text}')
    kit_context = entity.kind=='person' and bool(re.search(r'\b(?:jersey|kit|uniform)\b',moment.visual,re.I))
    value = (0.0 if kit_context else 2.0 * media.official) + (7.0 if kit_context else 2.0) * relevance(media, moment, entity)
    short = min(media.width, media.height) or 0
    value += min(1.0, short / (720 if media.kind == 'video' else 900))
    if moment.show == 'logo':
        value += 2.0 * (media.role == 'logo' or any(f' {w} ' in text for w in LOGO_WORDS))
        value += .5 * media.url.lower().split('?')[0].endswith('.png')     # usually transparent
    if moment.show == 'video':
        value += 1.5 * (media.kind == 'video')
    visual = _norm(moment.visual)
    value -= 1.5 * any(f' {w} ' in text and f' {w} ' not in visual for w in WEAK_WORDS)
    value -= .5 * media.nonfree * (moment.show != 'logo')
    return round(value, 3)


def _stock_media(candidate, query):
    """Stock result as Media. Its evidence text is only what the site says about the clip (page name,
    Pixabay tags): Pexels echoes our own query as the title, which would prove nothing."""
    slug = re.sub(r'[-_/]+', ' ', candidate.page_url.rstrip('/').rsplit('/', 1)[-1])
    slug = re.sub(r'\b\d+\b', ' ', slug).strip()
    own = slug if candidate.source == 'pexels' else f'{candidate.title} {slug}'
    return Media('video', candidate.source, candidate.id, slug or candidate.title or query, candidate.download_url,
                 candidate.thumb, candidate.page_url, candidate.width, candidate.height, candidate.duration,
                 candidate.author, STOCK_LICENSES.get(candidate.source, ''), '', own[:500], role='video')


def _safe(call, progress, what):
    try:
        return call() or []
    except PermissionError as error:
        raise error
    except Exception as error:
        progress(f'    {what} skipped: {error}')
        return []


def _is_logo(media):
    return any(f' {w} ' in _norm(f'{media.title} {media.text}') for w in LOGO_WORDS)


def gather(web, moment, entity, need, orientation, canvas, stock=(), progress=print, finder=None,
           *, reference_method=None):
    """Candidate media for one moment, best first. `need` = seconds of video the slot needs.
    `finder`: the web agent (WebSearch) that searches the whole internet; None = Wikimedia/stock only."""
    found = []
    label = entity.label or entity.name
    files = entity.files
    kinds = []
    if moment.show == 'logo':
        found += [_role(m, 'logo', True) for m in _safe(lambda: web.files(files.get('logo', [])), progress, 'Logo')]
        # The article's lead image is the logo for most apps/brands, but can be an office photo: only a
        # file named as a logo counts.
        lead = _safe(lambda: [web.lead_image(entity.wiki_title)], progress, 'Wikipedia image')
        found += [_role(m, 'logo', True) for m in lead if m and any(f' {w} ' in _norm(m.title) for w in LOGO_WORDS)]
        found += [m for m in _safe(lambda: web.commons_search(f'"{label}" logo', 'drawing', 12), progress, 'Commons')
                  if any(f' {w} ' in _norm(m.title) for w in LOGO_WORDS)]
        if finder is not None:      # "Zomato logo png" on the whole web, transparent PNGs first
            found += [m for m in _safe(lambda: finder.images(f'{label} logo png', 30, transparent=True),
                                       progress, 'Web logo search') if _is_logo(m)]
            found += [m for m in _safe(lambda: finder.images(f'{label} logo', 20), progress, 'Web logo search')
                      if _is_logo(m)]
        if not found and entity.website:
            found.append(web.site_icon(entity.website))
        kinds = ['image']
    else:
        if moment.show == 'video':
            found += [_role(m, 'video', True) for m in _safe(lambda: web.files(files.get('video', [])), progress, 'Video')]
            if finder is not None:  # web + YouTube: "Meenakshi Amman Temple", "Gandhi Salt March footage"
                for query in list(dict.fromkeys([moment.queries[0], label] + moment.queries[1:2])):
                    found += _safe(lambda: finder.videos(query, 12), progress, 'Web video search')
            found += _safe(lambda: web.commons_search(f'"{label}"', 'video', 20), progress, 'Commons video')
            for query in moment.queries:
                if _norm(query) != _norm(label):
                    found += _safe(lambda: web.commons_search(query, 'video', 12), progress, 'Commons video')
            if entity.kind in ('place', 'thing', 'event'):   # stock sites know landmarks, not people or brands
                for client in list(stock):
                    for query in moment.queries[:2]:
                        try:
                            results = client.search(query, orientation, canvas[0], canvas[1], 12)
                        except PermissionError as error:
                            progress(f'    {error} Skipping {client.name.title()}.')
                            stock.remove(client)
                            break
                        except Exception as error:
                            progress(f'    {client.name.title()} search skipped: {error}')
                            continue
                        found += [_stock_media(c, query) for c in results]
            kinds.append('video')
        # Photos: for photo moments, and as the fallback when no real footage exists.
        found += [_role(m, 'portrait', True) for m in _safe(lambda: web.files(files.get('portrait', [])), progress, 'Photo')]
        if entity.kind == 'place' and 'map' in _norm(moment.visual):
            found += [_role(m, 'map', True) for m in _safe(lambda: web.files(files.get('map', [])), progress, 'Map')]
        lead = _safe(lambda: [web.lead_image(entity.wiki_title)], progress, 'Wikipedia image')
        found += [_role(m, 'lead', True) for m in lead if m and not m.nonfree]
        if finder is not None:      # real photos from anywhere on the web
            # Preserve the planner's specific team/scene query. A bare name or
            # portrait query loses RCB/MI/KKR context before vision ever sees it.
            context=set(_norm(moment.visual).split())-set(_norm(label).split())-{'in','the','a','with','of','and'}
            queries=list(dict.fromkeys(moment.queries+[moment.visual]))
            queries.sort(key=lambda q:-len(set(_norm(q).split())&context))
            # A dedicated profile is often indexed under the bare canonical
            # name. It is a retrieval fallback only; the strict team/scene
            # pixel check still decides whether any returned image is offered.
            for query in list(dict.fromkeys(queries[:2]+[label])):
                found += _safe(lambda: finder.images(query, 30), progress, 'Web image search')
        found += _safe(lambda: web.commons_search(f'"{label}"', 'bitmap', 20), progress, 'Commons photos')
        for query in moment.queries[:2]:
            if _norm(query) != _norm(label):
                found += _safe(lambda: web.commons_search(query, 'bitmap', 12), progress, 'Commons photos')
        kinds.append('image')
    unique = {}
    enriched={}
    for m in found:
        if m is None or m.kind not in kinds or m.id in unique:
            continue
        short = min(m.width, m.height)
        if m.kind == 'image' and short and short < (96 if moment.show == 'logo' else 320):
            continue
        if m.kind == 'video' and ((m.duration and m.duration < need + .3) or (short and short < 200)
                                  or m.duration > 30 * 60):
            continue
        if (m.kind=='image' and generic_reference_allowed(reference_method,entity.kind,moment.show,entity.label or entity.name)
                and not locked(m,entity,reference_method=reference_method) and finder is not None
                and hasattr(finder,'source_evidence')):
            key=(m.id,m.page_url)
            if key not in enriched:
                enriched[key]=finder.source_evidence(m,reference_method)
            m=enriched[key]
        if not locked(m,entity,reference_method=reference_method) or not matches_event(m,moment,entity):
            continue
        m.score = score(m, moment, entity)
        unique[m.id] = m
    return sorted(unique.values(), key=lambda m: (-(m.kind == 'video' and moment.show == 'video'), -m.score))


def _role(media, role, official):
    if media is not None:
        media.role, media.official = role, official
    return media
