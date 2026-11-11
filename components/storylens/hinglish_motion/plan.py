"""Which moments get a motion graphic, which scene, and WHAT IT IS BUILT FROM: the local AI names the assets each
scene needs (the real person / logo / place, an object, a photo, a video clip) and a few short words. Motion
graphics here are pictures that move, not captions: most scenes must carry an asset. Hard rules check every answer
(fixed by the rules straight away where possible)."""
from dataclasses import asdict, dataclass, field
import math
import re
from pathlib import Path

from hinglish_eval import guard
from hinglish_eval.guard import Problem

ASSET_KINDS = ('person', 'brand', 'place', 'object', 'photo', 'clip')
# name: (what it is for, required fields, (min, max assets), asset kinds allowed, default mode)
TEMPLATES = {
    'cutout_hero': ('THE person / thing of the line, cut out, a huge word behind it (+ a handwritten note)',
                    ['word'], (1, 1), ('person', 'object', 'brand', 'place'), 'full'),
    'photo_card': ('a real photo as evidence (an event, a place, an old picture), taped on the page with a note',
                   ['label'], (1, 2), ('photo', 'person', 'place', 'object', 'brand'), 'full'),
    'spotlight': ('introduce a person or an idea: the cut-out pops out of a big colour circle, 2-line title',
                  ['title'], (1, 1), ('person', 'object', 'brand', 'place'), 'full'),
    'object_drop': ('an object that stands for the point (money, phone, watch, trophy...) drops in; a number if said',
                    ['title'], (1, 1), ('object', 'brand', 'photo'), 'overlay'),
    'collage': ('2-4 things named in the line, each a picture with its name', ['items'], (2, 4),
                ('object', 'brand', 'person', 'place', 'photo'), 'full'),
    'versus_assets': ('two things compared side by side (before / after, this vs that), a number under each if said',
                      ['left_label', 'right_label'], (2, 2), ('object', 'brand', 'person', 'place', 'photo'), 'full'),
    'frame_clip': ('real footage of an action or a place playing in a window', ['title'], (1, 1), ('clip', 'photo'), 'full'),
    'silhouette': ('an emotional / big-idea moment: the person or object as a glowing silhouette, one huge word',
                   ['word'], (1, 1), ('person', 'object', 'place'), 'full'),
    'route': ('a move or journey from one place to another (photos of both places on the map)', ['from', 'to'],
              (0, 2), ('place',), 'full'),
    # graphic elements without a downloaded asset
    'phone': ('an app screen: booking, payment, order, a price shown in an app', ['title', 'value'], (0, 0), (), 'full'),
    'call': ('someone calls and says something (who + the quoted words)', ['title', 'message'], (0, 0), (), 'full'),
    'chat': ('a short conversation, 2-4 messages', ['messages'], (0, 0), (), 'full'),
    'stamp': ('a verdict: CANCELLED, REJECTED, SOLD OUT, FAILED, APPROVED', ['stamp'], (0, 0), (), 'overlay'),
    'versus': ('two AMOUNTS compared (price promised vs asked)', ['left_value', 'right_value'], (0, 0), (), 'full'),
    'big_number': ('ONE striking number said in the line', ['value', 'label'], (0, 0), (), 'overlay'),
    'timeline': ('3-5 dated milestones (years)', ['title', 'years'], (0, 0), (), 'full'),
    'end_card': ('the closing line of the video (only at the end)', ['title'], (0, 0), (), 'full'),
    'headline': ('ONLY for a chapter title when nothing can be shown (rare)', ['title'], (0, 0), (), 'full'),
}
TEMPLATES['archive_board'] = ('Cricket documentary image story: choose a travelling timeline, film reel, centred image succession, hinged panels, album pages, print sheet or evidence fan; never force all looks into the same three-card collage', ['label'], (2, 4), ('person', 'photo'), 'full')
ARCHIVE_COMPOSITIONS = ('cinema', 'horizontal-reel', 'vertical-reel', 'road-travel', 'orbit', 'print-sheet', 'evidence-fan', 'hinged-triptych', 'turning-album')
from .creative import TEMPLATES as CREATIVE_TEMPLATES
TEMPLATES.update(CREATIVE_TEMPLATES)


def active_templates():
    from hinglish_niche.profiles import current_profile
    return {k: v for k, v in TEMPLATES.items() if k not in CREATIVE_TEMPLATES and (k != 'archive_board' or current_profile() == 'cricket')}


ASSET_TEMPLATES = {k for k, v in TEMPLATES.items() if v[2][1] > 0}
TEXT_ONLY = {'headline'}
LIMITS = {'kicker': 32, 'title': 22, 'title2': 24, 'subtitle': 40, 'label': 34, 'word': 12, 'value': 12, 'prefix': 4,
          'suffix': 10, 'caption': 60, 'left_label': 18, 'left_value': 10, 'left_prefix': 4, 'right_label': 18,
          'right_value': 10, 'right_prefix': 4, 'stamp': 14, 'app': 16, 'button': 16, 'message': 90, 'name': 26,
          'role': 34, 'from': 18, 'to': 18}
NUMBER_FIELDS = ('value', 'left_value', 'right_value')
NUMBER_WORDS = {'ek', 'do', 'teen', 'chaar', 'char', 'paanch', 'panch', 'chhe', 'saat', 'aath', 'nau', 'das', 'bees',
                'tees', 'chaalis', 'pachaas', 'sau', 'hazaar', 'hazar', 'lakh', 'crore', 'karod', 'one', 'two', 'three',
                'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand', 'million', 'billion',
                'gyaarah', 'baarah', 'terah', 'chaudah', 'pandrah', 'solah', 'satrah', 'athaarah', 'unnees', 'double',
                'half', 'aadha', 'dugna', 'percent', 'pratishat'}


@dataclass
class Scene:
    index: int
    line: int
    start: float
    duration: float
    text: str                      # what is said there
    template: str
    mode: str                      # full (replaces the picture) / overlay (over your video)
    data: dict = field(default_factory=dict)
    assets: list = field(default_factory=list)      # [{kind, query, name}] -> found files later
    why: str = ''

    def to_dict(self):
        return asdict(self)


def _clock(seconds):
    m, s = divmod(int(max(0, seconds)), 60)
    return f'{m}:{s:02d}'


def has_number(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return bool(re.search(r'\d', text)) or bool(words & NUMBER_WORDS)


def _norm(text):
    return re.sub(r'[^a-z0-9 ]+', ' ', str(text).lower())


ALIASES = {'delhi': ['dilli', 'dehli'], 'mumbai': ['bombay', 'mumbay'], 'bengaluru': ['bangalore', 'bengaluru', 'banglore'],
           'chennai': ['madras'], 'kolkata': ['calcutta', 'kolkatta'], 'tamil': ['tamil', 'tamizh'],
           'madurai': ['madurai', 'madhurai', 'madhu rahi'], 'india': ['bharat', 'hindustan'], 'rapido': ['rapid']}


def _sound(text):
    """Hinglish spellings vary (tamilnaadu / tamil nadu): compare without spaces and with doubled vowels collapsed."""
    t = _norm(text).replace(' ', '')
    for a, b in (('aa', 'a'), ('ee', 'i'), ('oo', 'u'), ('ii', 'i'), ('w', 'v'), ('sh', 's'), ('dh', 'd'), ('th', 't')):
        t = t.replace(a, b)
    return t


def name_said(name, said):
    """A real person / brand / place may only be shown when it is talked about (no invented celebrities)."""
    tokens = [t for t in _norm(name).split() if len(t) >= 3]
    text = f' {_norm(said)} '
    if not tokens:
        return False
    if any(f' {t}' in text or t in text.replace(' ', '') for t in tokens):
        return True
    sound = _sound(said)
    if any(_sound(t) in sound for t in tokens if len(t) >= 4):
        return True
    return any(any(_sound(a) in sound for a in ALIASES.get(t, [])) for t in tokens)


PLAN_SYSTEM = '''You are the motion-graphics designer of a Hinglish documentary / explainer channel. Motion graphics
are PICTURES THAT MOVE: real people cut out of photos, objects, logos, photos, video clips, maps and app screens,
animated with a few short words. They are NOT captions or subtitles: never just repeat the sentence as text.
You get part of a script as lines "[id] time text". For the chosen lines, pick ONE scene and name exactly which
assets it is built from. Scenes (use only these, with their fields):
{templates}
Assets: each is {{kind, query, name}}.
- kind: person (a real person talked about), brand (a company / app logo), place (a real city / building),
  object (ONE physical thing you could photograph alone on a table: money, a clock, a trophy, a phone, a motorbike,
  a key, a suitcase... never a place, a crowd, a scene or a document with writing),
  photo (a real scene / situation photo), clip (real video footage of an action or a place).
- query: English search words for exactly what must be visible, concrete and short, e.g. "thomas edison portrait
  old photo", "stack of indian rupee notes", "busy indian railway station crowd". No abstract words.
- name: the real name for person / brand / place (as written in the script), else "".
Rules:
- A real person, brand or place only when that name is said in these lines. Never invent people.
- Most scenes MUST carry assets (cutout_hero, photo_card, spotlight, object_drop, collage, versus_assets,
  frame_clip, silhouette, route). Use headline only when truly nothing can be shown.
- ALWAYS write the words of every scene: "word" (1 punchy word), "title" (2-4 words), "label" (a short note),
  plus the scene's own fields (items = the names under each collage picture, left_label/right_label, from/to).
  Hinglish in Roman letters or English, taken from what is said. Never show an internal scene/template name such
  as object_drop, photo_card or cutout_hero. Never put words inside the asset query.
- Every number shown must be SAID in that line. Never invent numbers, dates or facts.
- mode: "full" = the graphic fills the screen; "overlay" = over the speaker's video (object_drop, stamp, big_number).
- Vary the scenes: use each scene type at most 3 times; mix cut-outs, photo cards, spotlights, object drops,
  collages, versus, clips, maps and app screens. end_card only for the final lines.
- A brand asset is a real company / app named in the line (Zomato, HCL...), never a generic word like "company".
{coverage}'''
KEY_RULE = 'Choose about {count} key moments in this part (never two lines in a row; fewer if nothing deserves one).'
FULL_RULE = ('This is a FULL motion-graphics video: cover the WHOLE part, one scene for every 1-2 lines (about {count} '
             'scenes), in story order, starting with the first line.')


def plan_schema(count):
    text = {'type': 'string'}
    props = {k: text for k in LIMITS}
    props.update(line={'type': 'integer'}, why=text, template={'type': 'string', 'enum': list(active_templates())},
                 mode={'type': 'string', 'enum': ['full', 'overlay']},
                 items={'type': 'array', 'maxItems': 4, 'items': text},
                 years={'type': 'array', 'maxItems': 5, 'items': {'type': 'object', 'properties': {'year': text, 'text': text},
                                                                  'required': ['year', 'text']}},
                 messages={'type': 'array', 'maxItems': 4, 'items': {'type': 'object', 'properties': {'who': text, 'text': text},
                                                                     'required': ['who', 'text']}},
                 assets={'type': 'array', 'maxItems': 4, 'items': {'type': 'object', 'properties': {
                     'kind': {'type': 'string', 'enum': list(ASSET_KINDS)}, 'query': text, 'name': text},
                     'required': ['kind', 'query', 'name']}})
    from hinglish_niche.profiles import current_profile
    if current_profile() == 'cricket':
        props['archive_style'] = {'type': 'string', 'enum': ['slate', 'sepia', 'ink', 'map', 'glass', 'album', 'night']}
        props['archive_grade'] = {'type': 'string', 'enum': ['colour', 'monochrome']}
        props['archive_composition'] = {'type': 'string', 'enum': list(ARCHIVE_COMPOSITIONS)}
        props['assets']['items']['properties']['historical'] = {'type': 'object', 'properties': {
            'year': {'type': ['integer', 'null']}, 'team': text, 'match_id': text},
            'required': ['year', 'team', 'match_id']}
    return {'type': 'object', 'properties': {'moments': {'type': 'array', 'maxItems': count + 3, 'items': {
        'type': 'object', 'properties': props,
        'required': ['line', 'why', 'template', 'mode', 'word', 'title', 'label', 'assets']}}},
        'required': ['moments']}


def _said(by_id, line):
    return ' '.join(by_id[i].text for i in (line, line + 1) if i in by_id)


def moment_problems(m, by_id, last_ids, part_text):
    label = f'line {m.get("line")}'
    template = m.get('template')
    if m.get('line') not in by_id:
        return [Problem('motion.line', f'{label} is not in this part')]
    if template not in TEMPLATES:
        return [Problem('motion.template', f'{label}: unknown scene "{template}"')]
    _, required, (lo, hi), kinds, _ = TEMPLATES[template]
    problems = []
    for f in required:
        value = m.get(f)
        need = 2 if f in ('messages', 'items') else 3 if f == 'years' else 1
        if not value or (isinstance(value, list) and len(value) < need):
            problems.append(Problem('motion.fields', f'{label}: {template} needs "{f}"'))
    for f, limit in LIMITS.items():
        if isinstance(m.get(f), str) and len(m[f]) > limit:
            problems.append(Problem('motion.length', f'{label}: {f} is {len(m[f])} characters (at most {limit})'))
    for f in ('title', 'label', 'word', 'subtitle'):
        value = str(m.get(f) or '').strip().lower()
        if value and (value == str(template).lower() or value in TEMPLATES or '_' in value):
            problems.append(Problem('motion.visible_text',
                                    f'{label}: "{m[f]}" is an internal scene name, not words for the viewer'))
    said = _said(by_id, m['line'])
    for f in NUMBER_FIELDS:
        if m.get(f) and not has_number(said):
            problems.append(Problem('motion.no_invented_numbers', f'{label}: shows the number "{m[f]}" but the line '
                                                                  'says no number'))
    assets = [a for a in (m.get('assets') or []) if isinstance(a, dict)]
    if not lo <= len(assets) <= max(hi, lo):
        problems.append(Problem('motion.assets', f'{label}: {template} is built from {lo}-{hi} asset(s), not {len(assets)}'))
    if template == 'collage' and len(assets) != len(m.get('items') or []):
        problems.append(Problem('motion.assets', f'{label}: collage needs one picture per item'))
    for a in assets:
        if a.get('kind') not in ASSET_KINDS or (kinds and a.get('kind') not in kinds):
            problems.append(Problem('motion.assets', f'{label}: {template} cannot use a {a.get("kind")} asset'))
        if len(str(a.get('query', '')).strip()) < 3:
            problems.append(Problem('motion.assets', f'{label}: every asset needs search words (query)'))
        if a.get('kind') in ('brand', 'place') and not str(a.get('name', '')).strip():
            problems.append(Problem('motion.assets', f'{label}: a {a["kind"]} asset needs its real name'))
        if a.get('kind') in ('person', 'brand', 'place') and str(a.get('name', '')).strip():
            if not name_said(a['name'], part_text):
                problems.append(Problem('motion.no_invented_people', f'{label}: "{a["name"]}" is not talked about here'))
    if template == 'end_card' and m['line'] not in last_ids:
        problems.append(Problem('motion.end_card', f'{label}: end_card only for the last lines of the video', hard=False))
    return problems


def plan_rules(part, last_ids, full=False):
    by_id = {l.id: l for l in part}
    part_text = ' '.join(l.text for l in part)

    def checker(answer):
        problems, chosen, kinds = [], [], []
        for m in (answer or {}).get('moments') or []:
            problems += moment_problems(m, by_id, last_ids, part_text)
            if isinstance(m.get('line'), int):
                chosen.append(m['line'])
            kinds.append(m.get('template'))
        chosen.sort()
        if not full:
            close = [b for a, b in zip(chosen, chosen[1:]) if b - a < 2]
            if close:
                problems.append(Problem('motion.spacing', f'lines {close[:3]} are right after another graphic', hard=False))
        elif chosen:
            gaps = [b for a, b in zip([part[0].id - 1] + chosen, chosen + [part[-1].id + 1]) if b - a > 3]
            if gaps:
                problems.append(Problem('motion.coverage', f'the full video has no scene around lines {gaps[:3]}',
                                        hard=False))
        if kinds and sum(k in ASSET_TEMPLATES for k in kinds) < .6 * len(kinds):
            problems.append(Problem('motion.pictures', 'too few scenes carry a picture: use cut-outs, photos, objects and '
                                                       'clips, not text', hard=False))
        return problems
    return checker


def _trim(text, limit):
    text = ' '.join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0]
    return cut if len(cut) >= limit * .5 else text[:limit]


STOP = set("""aur to toh phir ab jab tab ki ke ka ko se ne mein me par pe hai hain tha thi the ho hoga yeh ye woh wo
vo bhi nahin nahi na main mujhe mera mere meri hum tum aap kya kaise kyun koi kuch ek do bas hi hua hui hue kar karna
kiya diya liya raha rahi rahe tak lie liye wala wali vala vali and the a an of to in on is are was so but that this with
for my i you it haan han yahaan yahan vahan wahan vahi wahi abhi sab mainne maine usne unhone hoon paas baad gaya
gayi gaye hota hoti karte karta karti dekha dekhie dekhna jaanta bhej bheja lekin magar agar""".split())
QUOTED = re.compile(r"""(with\s+)?(the\s+)?['"“”‘’][^'"“”‘’]{1,40}['"“”‘’](\s+(word|text|written)[^,.]*)?""", re.I)


def clean_query(query):
    """Search words describe a picture; words to show go on screen, not into the picture."""
    q = QUOTED.sub(' ', str(query))
    q = re.sub(r'\b(with|showing)\s+(the\s+)?(word|text|words|caption)s?\b.*$', ' ', q, flags=re.I)
    return ' '.join(q.split())[:70]


def _content_words(text):
    return [w for w in re.findall(r"[A-Za-z0-9₹%]+", text) if w.lower() not in STOP and len(w) >= 3]


def _short(text, limit, words=4):
    return _trim(' '.join(_content_words(text)[:words]), limit)


def autofill(part, last_ids):
    """Fill the words the model left out from what is said there, fix asset kinds and search words, keep only
    names that are talked about (the other pictures stay). Never drops a scene."""
    by_id = {l.id: l for l in part}
    part_text = ' '.join(l.text for l in part)

    def fill(answer):
        fixes, out = [], []
        for m in (answer or {}).get('moments') or []:
            if not isinstance(m, dict):
                continue
            m = dict(m)
            line = by_id.get(m.get('line'))
            said = line.text if line else ''
            template = m.get('template')
            for f, limit in LIMITS.items():                 # too long: shortened at a word boundary
                if isinstance(m.get(f), str):
                    m[f] = _trim(m[f], limit)
            if isinstance(m.get('items'), list):
                m['items'] = [_trim(i, 22) for i in m['items'] if str(i).strip()][:4]
            if not has_number(' '.join(by_id[i].text for i in (m.get('line'), (m.get('line') or 0) + 1) if i in by_id)):
                for f in NUMBER_FIELDS:                      # a number that is not said is removed, not shown
                    if m.get(f):
                        fixes.append(f'line {m.get("line")}: removed the unsaid number {m[f]}')
                        m[f] = ''
            assets = []
            for a in (m.get('assets') or []):
                if not isinstance(a, dict):
                    continue
                historical = a.get('historical')
                a = {'kind': a.get('kind') if a.get('kind') in ASSET_KINDS else 'object',
                     'query': clean_query(a.get('query', '')), 'name': ' '.join(str(a.get('name') or '').split())[:40]}
                from hinglish_niche.profiles import current_profile
                if current_profile() == 'cricket' and isinstance(historical, dict):
                    a['historical'] = historical
                if a['kind'] in ('person', 'brand', 'place') and a['name'] and not name_said(a['name'], part_text):
                    fixes.append(f'line {m.get("line")}: dropped "{a["name"]}" (not said)')   # never a named stranger
                    continue
                if a['kind'] in ('brand', 'place') and not a['name']:
                    a['kind'] = 'photo' if a['kind'] == 'place' else 'object'
                if len(a['query']) < 3:
                    a['query'] = a['name'] or _short(said, 40, 3)
                if template in TEMPLATES:
                    kinds = TEMPLATES[template][3]
                    if a['kind'] == 'clip' and template != 'frame_clip':
                        a['kind'] = 'photo'
                    elif kinds and a['kind'] not in kinds:
                        a['kind'] = 'photo' if 'photo' in kinds else kinds[0]
                assets.append(a)
            m['assets'] = assets
            names = [a['name'] or _short(a['query'], 22, 2) for a in assets]
            if not m.get('word'):
                m['word'] = (assets[0]['name'] if assets and assets[0]['name'] else '') or \
                    max(_content_words(said) or [''], key=len)
            m['word'] = (str(m['word']).split() or [''])[0][:12]
            if not m.get('title'):
                m['title'] = _short(said, 22, 3)
            if not m.get('label'):
                m['label'] = _short(said, 34, 5)
            for f, words in (('title', 3), ('label', 5), ('word', 1), ('subtitle', 5)):
                value = str(m.get(f) or '').strip().lower()
                if value and (value == str(template).lower() or value in TEMPLATES or '_' in value):
                    m[f] = _short(said, LIMITS[f], words)
                    fixes.append(f'line {m.get("line")}: replaced internal scene name in {f}')
            if template == 'collage' and len(m.get('items') or []) != len(assets):
                m['items'] = [n.title()[:22] for n in names]
            if template == 'versus_assets':
                m['left_label'] = m.get('left_label') or (names[0].title()[:18] if names else '')
                m['right_label'] = m.get('right_label') or (names[1].title()[:18] if len(names) > 1 else '')
            if template == 'route':
                places = [a['name'] for a in assets if a['kind'] == 'place' and a['name']]
                m['from'] = m.get('from') or (places[0] if places else '')
                m['to'] = m.get('to') or (places[1] if len(places) > 1 else '')
                if not (m['from'] and m['to']) and assets:          # one place only: its photo instead of a map
                    m['template'], m['assets'] = 'photo_card', assets[:1]
                    m['label'] = m.get('label') or m['from'] or m['to']
            if template == 'silhouette' and not any(a['kind'] == 'person' for a in assets):
                m['template'] = 'cutout_hero'              # only a person reads as a silhouette
            out.append(m)
        # variety: the same picture scene more than 3 times becomes the next unused picture scene
        used, cycle = {}, ['photo_card', 'spotlight', 'object_drop', 'cutout_hero']
        for m in out:
            t = m.get('template')
            used[t] = used.get(t, 0) + 1
            if t in ('cutout_hero', 'spotlight', 'object_drop', 'photo_card') and used[t] > 3:
                for alt in cycle:
                    kinds = TEMPLATES[alt][3]
                    if used.get(alt, 0) < 3 and all(a['kind'] in kinds for a in m['assets']):
                        used[t] -= 1
                        used[alt] = used.get(alt, 0) + 1
                        m['template'] = alt
                        m.setdefault('title', m.get('word') or '')
                        fixes.append(f'line {m.get("line")}: {t} -> {alt} (variety)')
                        break
        return {'moments': out}, fixes
    return fill


def plan_repair(part, last_ids, count, full=False):
    by_id = {l.id: l for l in part}
    part_text = ' '.join(l.text for l in part)

    fill = autofill(part, last_ids)

    def repair(answer):
        answer, fixes = fill(answer)
        kept, used = [], set()
        for m in (answer or {}).get('moments') or []:
            m = dict(m)
            for f, limit in LIMITS.items():
                if isinstance(m.get(f), str):
                    m[f] = _trim(m[f], limit)
            if isinstance(m.get('word'), str) and ' ' in m['word'].strip():
                m['word'] = m['word'].split()[0]
            if isinstance(m.get('items'), list):
                m['items'] = [_trim(i, 22) for i in m['items'] if str(i).strip()][:4]
            if isinstance(m.get('years'), list):
                m['years'] = [{'year': _trim(y.get('year', ''), 8), 'text': _trim(y.get('text', ''), 40)}
                              for y in m['years'] if isinstance(y, dict)][:5]
            if isinstance(m.get('messages'), list):
                m['messages'] = [{'who': _trim(x.get('who', ''), 14), 'text': _trim(x.get('text', ''), 60)}
                                 for x in m['messages'] if isinstance(x, dict)][:4]
            assets = [a for a in (m.get('assets') or []) if isinstance(a, dict)]
            # a real person / brand / place that is not talked about is dropped, never shown
            assets = [{'kind': a.get('kind'), 'query': _trim(a.get('query', ''), 70), 'name': _trim(a.get('name', ''), 40)}
                      for a in assets if not (a.get('kind') in ('person', 'brand', 'place') and
                                              not name_said(a.get('name', ''), part_text))]
            template = m.get('template')
            if template in TEMPLATES:
                lo, hi = TEMPLATES[template][2]
                if template == 'collage' and isinstance(m.get('items'), list):
                    n = min(len(assets), len(m['items']))
                    assets, m['items'] = assets[:n], m['items'][:n]
                assets = assets[:hi] if hi else []
                if len(assets) == 1 and template in ('collage', 'versus_assets'):
                    template = m['template'] = 'cutout_hero' if assets[0]['kind'] != 'photo' else 'photo_card'
                    first = (m.get('items') or [''])[0] if isinstance(m.get('items'), list) else ''
                    m['word'] = m.get('word') or (_trim(m.get('title') or first or m.get('left_label') or assets[0]['query'],
                                                        12).split(' ') or [''])[0]
                    m['label'] = m.get('label') or ''
                    if template == 'photo_card' and not m['label']:
                        m['label'] = _trim(m.get('title') or m.get('word') or '', 34)
            m['assets'] = assets
            if template in TEMPLATES and m.get('mode') not in ('full', 'overlay'):
                m['mode'] = TEMPLATES[template][4]
            if template == 'end_card' and m.get('line') not in last_ids:
                m['template'] = 'headline'
            hard = [p for p in moment_problems(m, by_id, last_ids, part_text) if p.hard]
            if hard or m.get('line') in used or len(kept) >= count + 2:
                fixes.append(f'dropped line {m.get("line")}' + (f' ({hard[0].rule})' if hard else ''))
                continue
            kept.append(m)
            used.add(m['line'])
        return {'moments': sorted(kept, key=lambda m: m['line'])}, fixes
    return repair


def scene_data(m):
    """AI answer -> the template's data (the assets are found and added later)."""
    data = {k: m[k] for k in LIMITS if isinstance(m.get(k), str) and m[k].strip()}
    if m['template'] == 'archive_board':
        data['archive_style'] = m.get('archive_style') if m.get('archive_style') in ('slate', 'sepia', 'ink', 'map', 'glass', 'album', 'night') else 'slate'
        data['archive_grade'] = m.get('archive_grade') if m.get('archive_grade') in ('colour', 'monochrome') else 'colour'
        if m.get('archive_composition') in ARCHIVE_COMPOSITIONS:
            data['archive_composition'] = m['archive_composition']
    if m['template'] in ('headline', 'end_card'):
        data['lines'] = [x for x in (m.get('title'), m.get('title2')) if x]
    if m['template'] in ('collage',):
        data['items'] = m.get('items') or []
    if m['template'] == 'timeline':
        data['items'] = m.get('years') or []
    if m['template'] == 'chat':
        data['messages'] = m.get('messages') or []
    return data


def plan_scenes(brain, lines, settings, progress=print, full=False):
    if not lines:
        raise ValueError('No script text or speech was found')
    from .creative import STYLES as creative_styles, plan_creative, planning_guidance
    if settings.style in creative_styles:
        return plan_creative(brain, lines, settings, progress, full=full)
    seconds = max(1.0, lines[-1].end - lines[0].start)
    total = math.ceil(len(lines) / 1.6) if full else settings.target(seconds)
    last_ids = {l.id for l in lines if l.start >= lines[0].start + seconds * .8} | {lines[-1].id}
    templates = '\n'.join(f'- {name}: {info[0]}. Fields: {", ".join(info[1])}' +
                          (f'; assets: {info[2][0]}-{info[2][1]} of {"/".join(info[3])}' if info[2][1] else '; no assets')
                          for name, info in active_templates().items())
    parts = [lines[i:i + 30] for i in range(0, len(lines), 30)]
    scenes, left = [], total
    for n, part in enumerate(parts, 1):
        if left <= 0:
            break
        count = math.ceil(len(part) / 1.6) if full else \
            max(1, min(left, round(total * (part[-1].end - part[0].start) / seconds + .3)))
        progress(f'Designing motion graphics {n}/{len(parts)} ({_clock(part[0].start)}-{_clock(part[-1].end)})')
        data = {'script_part': '\n'.join(f'[{l.id}] {_clock(l.start)} {l.text}' for l in part),
                'final_lines_of_video': sorted(i for i in last_ids if any(l.id == i for l in part))}
        data['creative_guidance'] = planning_guidance('motion', ' '.join(l.text for l in part))
        from .capabilities import connections
        data['connected_tools'] = connections(getattr(brain, 'root', None) or Path(__file__).resolve().parents[1])
        if hasattr(brain, 'root'):
            from hinglish_niche.style_memory import planning_examples
            examples = planning_examples(brain.root, ' '.join(l.text for l in part), purpose='motion')
            if examples:
                data['documentary_editing_examples'] = examples
        repair, fill = plan_repair(part, last_ids, count, full), autofill(part, last_ids)

        def ask(system, payload, schema, **options):
            # the words the model forgot are filled in; what the rules cannot fix goes back to the model,
            # and only its final answer is trimmed by dropping (repair)
            answer, fixes = fill(brain.json(system, payload, schema, **options))
            if fixes:
                progress('  Rules fixed: ' + '; '.join(fixes[:4]))
            return answer
        system = PLAN_SYSTEM.format(templates=templates, coverage=(FULL_RULE if full else KEY_RULE).format(count=count))
        answer = guard.ask_checked(ask, system, data, plan_schema(count), plan_rules(part, last_ids, full),
                                   label=f'motion graphics {n}', feature='motion', progress=progress, repair=repair,
                                   max_tokens=5000)
        by_id = {l.id: l for l in part}
        picked = answer.get('moments') or []
        if not full:
            picked = picked[:max(0, left)]
        for m in picked:
            line = by_id[m['line']]
            scenes.append(Scene(len(scenes) + 1, line.id, line.start, 0.0, line.text, m['template'],
                                m.get('mode') or TEMPLATES[m['template']][4], scene_data(m),
                                [dict(a) for a in m.get('assets') or []], str(m.get('why', ''))))
        left -= len(picked)
        progress(f'  {len(picked)} graphic(s): ' + ', '.join(m['template'] for m in picked))
    from hinglish_niche.historical import attach_context
    attach_context(scenes, lines)
    return scenes
