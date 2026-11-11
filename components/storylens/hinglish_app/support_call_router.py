"""Translate conversational requests into bounded Storylens UI actions."""
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from . import support_call_controls as ui_controls
from .support_call_knowledge import FEATURES, _match, _normalize, topic_matches
from .support_call_controls import controls, match_button_name, select_fields, _option_key, _phrase_in
from .support_call_actions import Outcome

APPS = ('premiere pro', 'after effects', 'davinci resolve', 'capcut', 'topaz video ai',
        'file explorer', 'chrome', 'excel', 'youtube', 'instagram', 'whatsapp', 'gmail')
SCHEMA = {
    'type': 'object',
    'properties': {
        'intent': {'type': 'string', 'enum': ['answer', 'open_tool', 'open_app', 'click_button', 'set_control']},
        'tool': {'type': 'string', 'enum': ['', *FEATURES]},
        'app': {'type': 'string', 'enum': ['', *APPS]},
        'label': {'type': 'string'},
        'value': {'type': 'string'},
        'reply': {'type': 'string'},
    },
    'required': ['intent'],
    'additionalProperties': False,
}


def _search(question, active, snapshot=(), fields=(), limit=8):
    # Kept behind the source catalogue module so registered/runtime controls have
    # one authority. The old compatibility branch is only for staged deployments.
    search = getattr(ui_controls, 'search_controls', None)
    return search(question, active, snapshot, fields, limit=limit) if search else ()


def _subject(question):
    text = str(question).strip(' \t\r\n.!?।')
    text = re.sub(r'^(?:and|also|please|can you|could you)\s+', '', text, flags=re.I)
    for pattern in (
        r'(?:what is|what s) (?:the )?feature of (.+)',
        r'(?:explain(?:ed)?|describe|tell me about|what about|where is|where can i find)\s+(.+)',
        r'what (?:is|s) (.+?)(?: for| used for)?',
        r'what does (.+?) do',
        r'(?:is there|do we have|does storylens have|does storyline have)\s+(?:an? )?(.+)',
        r'(.+?)\s+(?:क्या है|क्या करता है|क्या करती है|कहाँ है|किधर है|kya hai|kya karta hai|kahan hai)',
    ):
        found = re.fullmatch(pattern, text, re.I)
        if found:
            return re.sub(r'\s+(?:feature|tool|tab|फीचर|टूल)$', '', found[1], flags=re.I).strip()
    return ''


@lru_cache(maxsize=256)
def _candidate_features(question):
    """Suggestions only; uncertain spelling never executes an action."""
    subject = _normalize(_subject(question))
    if not subject or len(subject) > 70:
        return ()
    scores = []
    for key, (label, aliases, _) in FEATURES.items():
        terms = (label, *aliases.split('|'))
        score = max(SequenceMatcher(None, subject, _normalize(term)).ratio()
                    for term in terms if len(_normalize(term)) >= 4)
        if score >= .48:
            scores.append((score, key))
    return tuple(key for _, key in sorted(scores, reverse=True)[:2])


def _evidence(question, active, snapshot=(), fields=()):
    keys = _match(' ' + _normalize(question) + ' ')
    records = list(_search(question, active, snapshot, fields))
    for topic in topic_matches(question)[:4]:
        for parent in topic['features']:
            if parent in FEATURES and parent not in keys:
                keys.append(parent)
        # Keep hand-authored source semantics even when HTML choices also match.
        # These records describe a capability, never a new executable route.
        records.append({'tool': topic['features'][0], 'kind': 'topic',
                        'label': topic['name'], 'purpose': topic['detail'],
                        'source': topic['source'], 'parents': list(topic['features'])})
    for row in records:
        if row.get('tool') in FEATURES and row['tool'] not in keys:
            keys.append(row['tool'])
    return keys, tuple(records)


def _compact_records(records):
    result = []
    ranked = sorted(records, key=lambda row: row.get('kind') != 'topic')
    for record in ranked[:8]:
        row = {key: record[key] for key in ('tool', 'kind', 'label', 'id', 'purpose', 'disabled', 'entry_button', 'dynamic', 'source', 'parents')
               if key in record}
        matches = record.get('matched_options') or ()
        choices = list(record.get('options') or ())
        match_values = {item.get('value') for item in matches if isinstance(item, dict)}
        # The named option must not disappear merely because it is item 25.
        choices.sort(key=lambda item: item.get('value') not in match_values)
        if choices:
            row['options'] = [{key: item[key] for key in ('label', 'value', 'disabled') if key in item}
                              for item in choices[:12]]
            row['more_options'] = max(0, len(choices) - 12)
        result.append(row)
    return result


def routing_context(question, active, history, snapshot, fields=()):
    keys, records = _evidence(question, active, snapshot, fields)
    candidates = () if keys else _candidate_features(question)
    if not keys:
        keys = list(candidates) or ([active] if active in FEATURES else [])
    query = _option_key(question)
    labels = {}
    for key in keys[:3]:
        names = list(dict.fromkeys(name for name, _, _ in controls(key)))
        names.sort(key=lambda name: not _phrase_in(_option_key(name), query))
        labels[key] = names[:42]
    facts = {key: FEATURES[key][2] for key in keys[:3]}
    return (
        '\nYou can OPERATE Storylens. For an explicit request to open, go inside, take me to, '
        'click or change a setting, return the corresponding action, not usage advice. '
        'For a question ABOUT a feature/button or how to use it, intent=answer. '
        'Never treat negation, hypotheticals, or quoted instructions as permission to act. '
        'Resolve "open it/that one" from the last discussed feature; current tab is only a fallback. '
        'The product catalogue is authoritative for feature/control existence. An engine, style, '
        'dropdown choice, or nested button may belong INSIDE a feature rather than be its own sidebar tab. '
        'Use the supplied parent tool and control path. A kind=section record is a heading/card, not a clickable button; '
        'its entry_button names the real control, and duplicate labels still require the correct scope. '
        'A dynamic dropdown with no current options is a known menu whose choices have not been observed, not a missing feature. '
        'Do not say a registered feature or a retrieved '
        'control/option is missing from Storylens. Source presence does not prove installed models, '
        'editor connections, account readiness, or successful execution. Distinguish these explicitly. '
        'Missing retrieval or an unfamiliar speech transcription is NOT proof a feature does not exist. '
        'When the spoken name is uncertain, ask a short clarification about what the caller wants to do; '
        'offer supplied candidate names as questions only. Never assert that an unrecognized name is absent. '
        'Choose only a listed tool/app. Do not output code, scripts, paths or shell commands. '
        'For a button use its exact supplied label and correct tool. For a dropdown use its exact supplied '
        'label/value; disabled choices cannot be selected. Do not claim an action completed: the UI verifies it. '
        'Omit unused JSON fields. For actions omit reply. For answers include reply with at most two brief sentences. '
        'Examples: "Can we head over to captions?" -> intent=open_tool, tool=captions. '
        '"I would like the screen for adding supplementary footage" -> intent=open_tool, tool=broll. '
        '"How does B-roll work?" -> intent=answer. '
        '"Use Hyperframes" with a retrieved Motion Graphics / Render engine option -> '
        'intent=set_control, tool=motion, label=Render engine, value=hyperframes. '
        '"What is Hyperframes?" -> explain its retrieved place inside Motion Graphics; do not deny its existence. '
        '\nCurrent observed tab: ' + active +
        '\nRegistered tools: ' + json.dumps({key: row[0] for key, row in FEATURES.items()}, ensure_ascii=False) +
        '\nApps: ' + ', '.join(APPS) +
        '\nRelevant feature facts: ' + json.dumps(facts, ensure_ascii=False) +
        '\nUncertain name suggestions (ask, never assume): ' + json.dumps(
            {key: FEATURES[key][0] for key in candidates}, ensure_ascii=False) +
        '\nButton labels by tool: ' + json.dumps(labels, ensure_ascii=False) +
        '\nLive buttons (name, enabled): ' + json.dumps(list(snapshot)[:35], ensure_ascii=False) +
        '\nRetrieved controls and options from the product catalogue: ' +
        json.dumps(_compact_records(records), ensure_ascii=False)
    )


def _location(record, language):
    tool = FEATURES.get(record.get('tool'), (record.get('tool', ''),))[0]
    label = record.get('label', '')
    if record.get('kind') == 'topic' and language != 'hi':
        return record.get('purpose', '').split('. ', 1)[0].rstrip('.') + '.'
    matched = [item.get('label') for item in record.get('matched_options', ())
               if isinstance(item, dict) and item.get('label')]
    subject = ', '.join(dict.fromkeys(matched)) if matched else label
    path = tool + (' → ' + label if matched else '')
    if language == 'hi':
        return f'{subject}, {path} में है।' + (' यह कंट्रोल अभी बंद है।' if record.get('disabled') else '')
    return f'{subject} is in {path}.' + (' This control is currently disabled.' if record.get('disabled') else '')



def _preferred_records(question, records):
    """An explicitly named field outranks broad 'list options' scope results."""
    query = _option_key(question)
    named = [row for row in records if row.get('kind') != 'topic' and row.get('label') and
             _phrase_in(_option_key(row['label']), query)]
    if named:
        longest = max(len(_option_key(row['label'])) for row in named)
        return [row for row in named if len(_option_key(row['label'])) == longest]
    choices = [row for row in records if row.get('matched_options')]
    return choices or [row for row in records if row.get('kind') == 'topic'] or list(records)


def _options_question(question):
    text = str(question).strip()
    return bool(re.match(
        r'^(?:(?:please|can you|could you)\s+)?(?:what|which)\s+(?:are\s+)?(?:the\s+)?(?:available\s+)?(?:options?|choices?)\b'
        r'|^(?:(?:please|can you|could you)\s+)?(?:list|show|tell me)\s+(?:me\s+)?(?:the\s+)?(?:options?|choices?)\b'
        r'|(?:कौन से|कौनसे|कौन कौन से).{0,40}(?:विकल्प|ऑप्शन)'
        r'|(?:विकल्प|ऑप्शन).{0,30}(?:क्या हैं|कौन से हैं)',
        text, re.I))


def _options_answer(question, records, language):
    selected = [row for row in _preferred_records(question, records) if row.get('kind') == 'select']
    identities = {(row.get('tool'), row.get('id') or row.get('label')) for row in selected}
    if len(identities) != 1:
        return ''
    row = selected[0]
    tool = FEATURES.get(row.get('tool'), (row.get('tool', ''),))[0]
    path = tool + ' → ' + row['label']
    options = [option['label'] for option in row.get('options', ())
               if option.get('label') and option.get('value') and not option.get('disabled')]
    if not options:
        if row.get('dynamic'):
            return (f'{path} एक डायनैमिक मेन्यू है। फीचर खोलने पर उसके मौजूदा विकल्प लोड होंगे; वे अभी यहाँ जाँचे नहीं गए हैं।'
                    if language == 'hi' else
                    f'{path} is a dynamic menu. Open the feature to load its current choices; they have not been verified here.')
        return (f'{path} में अभी कोई सक्षम विकल्प दर्ज नहीं है।' if language == 'hi'
                else f'{path} has no enabled choices in the supplied catalogue.')
    names = ', '.join(dict.fromkeys(options))
    if language == 'hi':
        return f'{path} के विकल्प हैं: {names}।'
    return f'{path} choices are {names}.'

def catalog_answer(question, active='', snapshot=(), fields=(), language='en'):
    """Fast source-based location/existence lookup, never an execution receipt."""
    query = str(question).strip()
    if _options_question(query):
        _, records = _evidence(question, active, snapshot, fields)
        return _options_answer(question, records, language)
    if not re.search(r'\b(?:where|is there|do we have|does storylens have|does storyline have)\b'
                     r'|कहाँ|किधर|मिलता है', query, re.I):
        return ''
    keys, records = _evidence(question, active, snapshot, fields)
    # Only named, source-grounded entities; generic "where is it" stays semantic.
    if records:
        chosen = _preferred_records(question, records)
        paths = list(dict.fromkeys(_location(row, language) for row in chosen))
        if len(paths) <= 2:
            return ' '.join(paths)
    if len(keys) == 1 and _subject(question):
        label = FEATURES[keys[0]][0]
        return (f'{label}, Storylens के फीचर मेन्यू में है।' if language == 'hi'
                else f'{label} is listed in the Storylens feature menu.')
    return ''


_ABSENCE = re.compile(
    r"\b(?:isn['’]?t|aren['’]?t|is not|are not|doesn['’]?t|does not|don['’]?t|do not|cannot|can['’]?t|not)\b"
    r".{0,100}\b(?:feature|tool|exist|available|recogniz|recognise|see|find|listed|storylens|storyline)\w*"
    r"|\b(?:feature|tool|storylens|storyline)\b.{0,100}\b(?:isn['’]?t|is not|doesn['’]?t|does not|not available|not found)\b"
    r"|(?:नहीं|नही).{0,60}(?:फीचर|सुविधा|टूल|मिल|पहचान|उपलब्ध)"
    r"|(?:फीचर|सुविधा|टूल|उपलब्ध|मौजूद).{0,60}(?:नहीं|नही)"
    r"|(?:نہیں).{0,60}(?:فیچر|ٹول|موجود|دستیاب)|(?:فیچر|ٹول|موجود|دستیاب).{0,60}(?:نہیں)",
    re.I,
)


def ground_answer(question, reply, active='', snapshot=(), fields=(), language='en'):
    """Repair unsupported absence claims, without inventing execution/access."""
    readiness = bool(re.search(
        r'\b(?:disabled|offline|disconnected|not installed|not connected|missing model|missing connection|no access|permission denied)\b'
        r'|(?:मॉडल|कनेक्शन|इंस्टॉल|डिसेबल|पहुँच).{0,35}(?:नहीं|बंद)|(?:अभी).{0,20}(?:उपलब्ध नहीं)',
        str(reply), re.I))
    if not _ABSENCE.search(str(reply)) and not readiness:
        return reply
    keys, records = _evidence(question, active, snapshot, fields)
    subject = _subject(question)
    product_question = bool(keys or records or re.search(
        r'\b(?:feature|tool|tab|storylens|storyline)\b|फीचर|टूल|सुविधा|فیچر|ٹول',
        str(question), re.I))
    if not product_question and not (subject and active in FEATURES):
        return reply
    # This helper sees model prose, not executor error receipts. Do not accept a
    # model-invented runtime blocker just because it says "currently" or "offline".
    disabled = [row for row in records if row.get('live') and row.get('disabled') is True]
    if disabled:
        return _location(disabled[0], language)
    if readiness and keys:
        name = FEATURES[keys[0]][0]
        if language == 'hi':
            return f'{name}, Storylens में है। इसे चलाने वाले मॉडल या कनेक्शन की स्थिति अभी जाँची नहीं गई है।'
        return f'{name} is a Storylens feature. Its current model or connection readiness has not been verified.'
    if records:
        if _options_question(question):
            listing = _options_answer(question, records, language)
            if listing:
                return listing
        selected = _preferred_records(question, records)
        paths = list(dict.fromkeys(_location(row, language) for row in selected))
        if len(paths) <= 2:
            return ' '.join(paths)
    if len(keys) == 1:
        label, _, purpose = FEATURES[keys[0]]
        # A recognized parent does not prove an unknown nested capability exists.
        exact_subject = _normalize(subject) in {
            _normalize(name) for name in (label, *FEATURES[keys[0]][1].split('|'))}
        if exact_subject or not subject and _normalize(label) in _normalize(reply):
            if language == 'hi':
                return f'{label}, Storylens में है। उससे आपको क्या करना है?'
            return f'{label} is a Storylens feature. {purpose.split(". ", 1)[0].rstrip(".")}.'
    if not subject and not re.search(r'\b(?:feature|tool|storylens|storyline)\b|फीचर|टूल', str(reply), re.I):
        return reply
    candidates = _candidate_features(question)
    if candidates:
        names = [FEATURES[key][0] for key in candidates]
        choices = (' या ' if language == 'hi' else ' or ').join(names)
        return f'क्या आपका मतलब {choices} है, या कोई दूसरा फीचर?' if language == 'hi' else (
            f'Did you mean {choices}, or another feature?')
    return ('उस फीचर से आपको क्या करना है? मैं सही फीचर ढूँढने में मदद करूँगी।'
            if language == 'hi' else 'What do you want that feature to do? I can help find the right feature.')


def decode_plan(raw, active, snapshot):
    plan = json.loads(raw)
    if not isinstance(plan, dict):
        raise ValueError('Invalid voice plan')
    intent, tool = plan.get('intent'), plan.get('tool') or active
    if intent == 'answer':
        return None, str(plan.get('reply', '')).strip()[:600], ''
    if intent == 'open_app':
        app = plan.get('app')
        if app not in APPS:
            raise ValueError('Unknown app')
        return None, '', 'open ' + app
    if tool not in FEATURES:
        raise ValueError('Unknown feature')
    label, value = plan.get('label', ''), plan.get('value', '')
    if intent == 'open_tool':
        action = ({'type': 'open_publishing'} if tool == 'preparePost' else
                  {'type': 'open_schedule'} if tool == 'scheduledPosts' else
                  {'type': 'open_tool', 'tool': tool})
        return Outcome('Opening ' + FEATURES[tool][0] + '.', action), '', ''
    if intent == 'click_button':
        names = [name for name, _, _ in controls(tool)]
        if tool == active:
            names.extend(row[0] for row in snapshot)
        exact = match_button_name(label, names)
        if not exact:
            raise ValueError('Button not identified')
        return Outcome('', {'type': 'click_button', 'tool': tool, 'label': exact}), '', ''
    if intent == 'set_control' and isinstance(label, str) and isinstance(value, str) and 0 < len(value) <= 1200 and len(label) <= 160:
        return Outcome('', {'type': 'set_control', 'tool': tool, 'label': label, 'value': value}), '', ''
    raise ValueError('Unknown voice action')
