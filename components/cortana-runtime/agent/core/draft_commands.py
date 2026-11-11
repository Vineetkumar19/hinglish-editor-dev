"""Parse explicit, literal communication commands without inventing message text."""
import re

_SPELLING_WORDS = dict(zip(
    'alfa bravo charlie delta echo foxtrot golf hotel india juliett kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu'.split(),
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
))
_SPELLING_WORDS.update(alpha='A', juliet='J')


def parse_recipient_correction(message):
    spelling = re.fullmatch(
        r'(?:spell|set|tell|bell|belt) (?:the )?(?:contact name|recipient)\s+as\s+([a-z][a-z\s,.-]{0,160})[.!?]*',
        message.strip(), re.I,
    )
    if spelling:
        spoken_name = spelling[1].strip(' .')
        repetition = re.fullmatch(r'(.{2,80})\.\s+\1', spoken_name, re.I)
        words = re.findall(r'[a-z]+', (repetition[1] if repetition else spoken_name).lower())
        if len(words) == 1:
            return words[0]
        if 2 <= len(words) <= 30 and all(len(word) == 1 or word in _SPELLING_WORDS for word in words):
            return ''.join(_SPELLING_WORDS.get(word, word.upper()) for word in words)
    match = re.fullmatch(
        r"(?:no[, ]+)?(?:(?:the )?(?:contact name|recipient|name) is|(?:change|correct) (?:the )?recipient to|search (?:the )?name as)\s+"
        r"(?P<name>[\w@][\w .@'’()\-]{0,79})[.!?]*", message.strip(), re.I,
    )
    if not match:
        return None
    name = match['name'].strip(' .')
    if len(name.split()) > 5 or re.search(r'\b(?:send|saying|message|instead of|and|that)\b', name, re.I):
        return None
    return name


def parse_draft_command(message):
    text = re.sub(r"^\s*(?:hey\s+)?cortana[, ]+", "", message.strip(), flags=re.I)
    patterns = [
        r"^(?P<platform>whatsapp|instagram|insta|gmail|email)\s+(?:par|pe)\s+(?P<recipient>.+?)\s+ko\s+(?:message|msg|text)\s+(?:karo|kar\s+do|bhejo|bhej\s+do)\s*[,;:]?\s*(?P<body>.+)$",
        r"^(?P<platform>whatsapp|instagram|insta|gmail|email)(?:\s*[:,]\s*|\s+)(?:message|text|draft|write|compose|send(?:\s+a\s+message)?)\s+(?:to\s+)?(?P<recipient>.+?)\s+saying\s+(?P<body>.+)$",
        r"^(?:message|text|send\s+(?:a\s+)?message|draft\s+(?:a\s+)?message)\s+(?:to\s+)?(?P<recipient>.+?)\s+(?:on|using|via)\s+(?P<platform>whatsapp|instagram|insta|gmail|email)\s+saying\s+(?P<body>.+)$",
        r"^open\s+(?P<platform>whatsapp|instagram|insta|gmail)\s+(?:and|then)\s+(?:message|text|write\s+to)\s+(?P<recipient>.+?)\s+saying\s+(?P<body>.+)$",
    ]
    for pattern in patterns:
        found = re.fullmatch(pattern, text, re.I | re.S)
        if not found:
            continue
        data = found.groupdict()
        data['platform'] = {'insta': 'instagram', 'email': 'gmail'}.get(data['platform'].lower(), data['platform'].lower())
        data['recipient'] = data['recipient'].strip()
        body = data['body'].strip()
        if body.startswith(('"', '“')) and body.endswith(('"', '”')):
            body = body[1:-1]
        # Hindi dictation needs the language model's translation/transliteration.
        if re.search(r'[\u0900-\u097f]', body):
            return None
        data['body'], data['subject'] = body, ''
        return data
    return None


def parse_recipient_only(message):
    text = re.sub(r'^\s*(?:hey\s+)?cortana[, ]+', '', message.strip(), flags=re.I).rstrip('.!?')
    patterns = [
        r'^(?:write|draft|compose)(?:\s+(?:an?\s+)?(?:email|mail|message))?\s+(?:in|on|using)\s+(?P<platform>gmail|email|whatsapp|instagram|insta)\s+(?:to|for)\s+(?P<recipient>[^:]+)$',
        r'^(?:open\s+)?(?P<platform>whatsapp|instagram|insta|gmail|email)(?:\s+and|\s+then|[:,])?\s+(?:message|text|write\s+to)\s+(?P<recipient>[^:]+)$',
        r'^(?:message|text)\s+(?P<recipient>.+?)\s+(?:on|using|via)\s+(?P<platform>whatsapp|instagram|insta|gmail|email)$',
    ]
    for pattern in patterns:
        found = re.fullmatch(pattern, text, re.I)
        if found:
            data = found.groupdict()
            if re.search(r'\b(saying|say|that|with|body|subject)\b', data['recipient'], re.I):
                return None
            if re.search(r'\b(?:hello|hi|hey|namaste)[.!? ]*$', data['recipient'], re.I):
                return None  # A greeting suffix may be the message, not part of the name.
            data['platform'] = {'insta':'instagram', 'email':'gmail'}.get(data['platform'].lower(), data['platform'].lower())
            return data
    return None
