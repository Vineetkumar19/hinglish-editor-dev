"""Recognize explicit voice actions without passing model output to Windows."""
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryFile
from time import monotonic

from .support_call_knowledge import FEATURES, _normalize


_CORTANA_PYTHON = Path('D:/Cortana/agent/.venv/Scripts/python.exe')
_WORKER = Path(__file__).with_name('support_call_desktop.py')
_CANCELLED = ContextVar('voice_action_cancelled', default=None)
_APP_NAMES = {
    'दा विंची': 'davinci resolve', 'दा विंची रिजॉल्व': 'davinci resolve',
    'दा विंची रिज़ॉल्व': 'davinci resolve', 'दाविंची': 'davinci resolve',
    'davinci': 'davinci resolve', 'da vinci': 'davinci resolve', 'da vinci resolve': 'davinci resolve', 'davinci resolve studio': 'davinci resolve',
    'प्रीमियर': 'premiere pro', 'प्रीमियर प्रो': 'premiere pro', 'adobe premiere': 'premiere pro', 'premier pro': 'premiere pro',
    'कैपकट': 'capcut', 'कैप कट': 'capcut', 'cap cut': 'capcut', 'cap cut desktop': 'capcut',
    'आफ्टर इफेक्ट्स': 'after effects', 'आफ्टर इफेक्ट': 'after effects',
    'फाइल एक्सप्लोरर': 'file explorer', 'फ़ाइल एक्सप्लोरर': 'file explorer',
    'व्हाट्सऐप': 'whatsapp', 'व्हाट्सएप': 'whatsapp', 'व्हाट्सएप्प': 'whatsapp',
    'जीमेल': 'gmail', 'g mail': 'gmail', 'what s app': 'whatsapp', 'what sapp': 'whatsapp',
    'क्रोम': 'chrome', 'यूट्यूब': 'youtube', 'यू ट्यूब': 'youtube',
    'इंस्टाग्राम': 'instagram', 'topaz': 'topaz video ai',
    'topaz video': 'topaz video ai', 'topaz video ai pro': 'topaz video ai',
    'टोपाज़': 'topaz video ai', 'टोपाज': 'topaz video ai', 'टॉपाज़': 'topaz video ai',
    'adobe after effects': 'after effects', 'aftereffects': 'after effects',
    'after effects 2026': 'after effects',
    'आफ़्टर इफ़ेक्ट्स': 'after effects',
    'windows explorer': 'file explorer', 'windows file explorer': 'file explorer',
    'file explorer': 'file explorer', 'explorer': 'file explorer', 'google chrome': 'chrome', 'chrome browser': 'chrome',
    'google chrome browser': 'chrome', 'browser': 'chrome',
    'microsoft excel': 'excel', 'ms excel': 'excel', 'एक्सेल': 'excel', 'माइक्रोसॉफ्ट एक्सेल': 'excel',
    'whatsapp desktop': 'whatsapp', 'whats app': 'whatsapp',
}
_LABELS = {key: value[0] for key, value in FEATURES.items()}
_LABELS.update({'preparePost': 'Publishing Studio', 'scheduledPosts': 'Scheduled posts'})
_TOOL_NAMES = {}
for _key, (_label, _aliases, _) in FEATURES.items():
    for _term in (_label, *_aliases.split('|')):
        _TOOL_NAMES.setdefault(_normalize(_term), set()).add(_key)
_TOOL_NAMES['publishing studio'] = {'preparePost'}
_TOOL_NAMES['schedule posts'] = {'scheduledPosts'}
_TOOL_NAMES['scheduling'] = {'scheduledPosts'}
_TOOL_NAMES['scheduling tab'] = {'scheduledPosts'}
_TOOL_NAMES['शेड्यूल पोस्ट'] = {'scheduledPosts'}
_TOOL_NAMES['पब्लिशिंग स्टूडियो'] = {'preparePost'}

for _key, _variants in {
    'clean': 'स्मार्ट क्लीन|स्मार्ट क्लिन|remove silence',
    'script': 'स्मार्ट एडिट|स्क्रिप्ट एडिट',
    'captions': 'ऑटो कैप्शन्स|ऑटो कैप्शन',
    'matchCut': 'मैच कट फाइंडर|मैच कट',
    'introCreate': 'इंट्रो क्रिएट|इंट्रो बनाओ',
    'reelRecreate': 'रील रीक्रिएट|रील रीक्रिएशन',
    'referenceReel': 'रेफरेंस रील|रिफरेंस रील',
    'broll': 'ऐड बी रोल|बी रोल|bee roll|bee rolls|b rolls|broll|add bee roll',
    'visuals': 'स्मार्ट विज़ुअल्स|स्मार्ट विजुअल|स्मार्ट विजुअल्स',
    'zoom': 'स्मार्ट ज़ूम|स्मार्ट जूम',
    'sound': 'साउंड डिजाइन|साउंड डिज़ाइन',
    'eyecontact': 'आई कॉन्टैक्ट|आई कांटेक्ट',
    'shorts': 'लॉन्ग टू शॉर्ट्स|लॉन्ग टू शॉर्ट|लॉन्ग टु शॉर्ट्स|लॉंग टू शॉर्ट्स|long two shorts|log to shorts',
    'motion': 'मोशन ग्राफिक्स|मोशन ग्राफ़िक्स',
    'gaming': 'गेमिंग हाइलाइट्स|गेमिंग हाइलाइट',
    'thumbnail': 'थंबनेल|थम्बनेल',
    'cinematic': 'सिनेमैटिक फुटेज|सिनेमेटिक फुटेज',
    'slowMotion': 'सेलेक्टिव स्लो मोशन|सिलेक्टिव स्लो मोशन',
    'beats': 'बीट स्टूडियो',
    'downloader': 'डाउनलोडर',
    'photos': 'फोटो कलेक्टर|फ़ोटो कलेक्टर',
    'cricketDesk': 'क्रिकेट डेस्क',
    'gamingDesk': 'गेमिंग डेस्क',
    'callQA': 'कॉल क्यू ए|कॉल क्यूए',
    'editorLink': 'एडिटर हैंडऑफ|एडिटर हैंड ऑफ',
    'voiceover': 'वॉइस क्लोन|वॉइस ओवर|वॉइस क्लोनिंग|वॉइसओवर|वॉइस क्लोन',
    'colorGrade': 'कलर ग्रेड|कलर ग्रेडिंग',
    'templateImport': 'इम्पोर्ट टेम्पलेट|टेम्पलेट इम्पोर्ट',
    'templateAligner': 'टेम्पलेट अलाइनर',
    'templateText': 'टेम्पलेट टेक्स्ट',
    'presetLibrary': 'टेम्पलेट लाइब्रेरी|इफेक्ट लाइब्रेरी',
    'imageDownload': 'इमेज डाउनलोड',
    'scheduledPosts': 'शेड्यूल पोस्ट|शेड्यूल्ड पोस्ट|शेड्यूलिंग',
    'chatHistory': 'चैट्स|चैट हिस्ट्री',
    'profiles': 'प्रोफाइल|प्रोफ़ाइल',
    'storylensCall': 'वॉइस असिस्टेंट|वॉयस असिस्टेंट',
}.items():
    if _key in FEATURES:
        for _name in _variants.split('|'):
            _TOOL_NAMES[_normalize(_name)] = {_key}


_OPEN = r'(?:open|launch|start|take me (?:to|into|inside)|bring(?: me)? (?:up|to)|head (?:over )?(?:to|into)|go (?:to|inside|into)|switch to|navigate (?:to|into)|show me|kholo(?: do)?|khol do|खोलो|खोल दो|खोल दीजिए|खोल देना|खोलें|दिखाओ|ओपन(?: कर दो| करो| कर दीजिए)?)'
_NEGATIVE = re.compile(r"\b(?:don't|do not|never|nahi|nahin|mat)\b|मत खोल|नहीं खोल", re.I)
_PREPARE = re.compile(
    r'^(?:load|add|put|import|use|select)\s+(.+?)\s+(?:into|in|for|with)\s+(.+?)'
    r'(?:\s+and\s+(run|generate|start)(?:\s+it)?)?$', re.I)
_GENERATE = re.compile(r'^(?:run|generate|start)\s+(.+?)\s+(?:using|with|on)\s+(.+)$', re.I)
_HI_PREPARE = re.compile(
    r'^(.+?)\s+को\s+(.+?)\s+में\s+(?:डाल|जोड़|चुन|लोड)\s*(?:दो|करो|कर दो)?'
    r'(?:\s+और\s+(रन|जनरेट|शुरू)(?:\s+करो|\s+कर दो)?)?$', re.I)


@dataclass
class Outcome:
    text: str
    action: dict | None = None
    minimize: bool = False
    ok: bool = True


def _strip_command(text):
    value = text.strip(' \t,.!?।')
    value = re.sub(r"^(?:I (?:want|need|would like) (?:you )?to |I'd like (?:you )?to |will you |would you mind )", '', value, flags=re.I)
    value = re.sub(r'^(?:(?:hey|hi|okay|ok|alright|well|so|now|please|ज़रा|जरा|यार|भाई|चलो|चल|अब|तो|अच्छा|ठीक है|कृपया|मुझे|मेरे लिए|can you|could you|would you|can we|could we|let us|let s|(?:storylens|cortana)(?: ai)?|कोटाना|कॉर्टाना)[, ]+)+', '', value, flags=re.I)
    return re.sub(r'\s+(?:for me|please|प्लीज़|प्लीज)$', '', value, flags=re.I).strip()


_NEXT_ACTION = r'(?:open|launch|load|add|put|import|use|select|run|generate|start|go to|switch|set|change|enable|disable|turn|show me|navigate to|focus|bring forward|click|press|tap|hit|खोलो|ओपन|रन|जनरेट)'
_CHAIN_SEPARATOR = re.compile(
    rf'(?:[,.!?।]*\s+(?:and\s+then|then|after that|aur phir|phir|और फिर|उसके बाद|फिर)\s+'
    rf'|(?:\s+and\s+|\s+और\s+|[,.।]\s*)(?={_NEXT_ACTION}\b))',
    re.I,
)
_RUN_CURRENT = re.compile(
    r'^(?:run|generate|start)(?:\s+(?:it|this|the current tool|this tool|this feature))?$'
    r'|^(?:(?:इसे|इसको|इसी को)\s+)?(?:रन|जनरेट|शुरू)\s*(?:करो|कर दो|करें)?$',
    re.I,
)


def _navigation_target(value, active=''):
    match = re.fullmatch(rf'{_OPEN}\s+(.+)', _strip_command(value), re.I)
    if not match:
        return ''
    return _tool(match[1], active)


def split_steps(transcript):
    """Split explicit compound instructions, preserving literal drafts and quoted paths."""
    value = _strip_command(transcript)
    if re.match(r'^(?:draft|compose)\b', value, re.I) or _NEGATIVE.search(value):
        return [value]
    # A spoken restatement of the same feature is not a second import task.
    correction = re.split(r'[,।]\s*', value, maxsplit=1)
    if len(correction) == 2:
        first = _navigation_target(correction[0])
        if first and _tool(correction[1], '') == first:
            return [correction[0]]
    spans = re.split(r'("[^"]*"|“[^”]*”)', value)
    pieces = ['']
    for index, span in enumerate(spans):
        if index % 2:
            pieces[-1] += span
        else:
            parts = _CHAIN_SEPARATOR.split(span)
            pieces[-1] += parts[0]
            pieces.extend(parts[1:])
    steps = [_strip_command(piece) for piece in pieces if _strip_command(piece)]
    if steps and not (re.match(rf'{_NEXT_ACTION}\b', steps[0], re.I)
                      or re.search(r'(?:kholo|khol do|खोलो|खोल दो|ओपन करो)$', steps[0], re.I)):
        return [value]
    return steps


def _tool(value, active):
    name = _normalize(value)
    name = re.sub(r'^(?:(?:the|my)\s+)+', '', name)
    if name in {'it', 'that', 'that one', 'that feature', 'that tool', 'उसे', 'उसको', 'वो वाला', 'this tab', 'this tool', 'this feature', 'current tool', 'इस टैब', 'यह टैब', 'ये वाला फीचर', 'ये वाला'}:
        return active if active in FEATURES else ''
    names = _TOOL_NAMES.get(name) or _TOOL_NAMES.get(re.sub(r'\s+(?:tab|tool|feature|page|screen|section|टैब|टूल|फीचर)$', '', name), set())
    return next(iter(names)) if len(names) == 1 else ''


def _worker(kind, value='', **payload):
    cancelled = _CANCELLED.get()
    if cancelled is not None and cancelled.is_set():
        return {'ok': False, 'note': 'The call ended.'}
    if not _CORTANA_PYTHON.is_file():
        return {'ok': False, 'note': 'The installed Cortana desktop tools are unavailable.'}
    allowed_env = {'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'USERPROFILE', 'USERNAME', 'APPDATA',
                   'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'HOMEDRIVE',
                   'HOMEPATH', 'SYSTEMDRIVE', 'TEMP', 'TMP', 'ONEDRIVE', 'COMPUTERNAME'}
    env = {key: val for key, val in os.environ.items() if key.upper() in allowed_env}
    try:
        with TemporaryFile() as output:
            args = [str(_CORTANA_PYTHON), '-I', '-B', str(_WORKER)]
            with subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL,
                env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            ) as process:
                process.stdin.write(json.dumps({'kind': kind, 'value': value, **payload}).encode('utf-8'))
                process.stdin.close()
                deadline = monotonic() + 40
                while process.poll() is None:
                    if monotonic() >= deadline or (cancelled is not None and cancelled.is_set()):
                        _stop_worker(process)
                        return {'ok': False, 'note': 'The desktop request stopped.'}
                    try:
                        process.wait(timeout=0.15)
                    except subprocess.TimeoutExpired:
                        pass
                returncode = process.returncode
            output.seek(0)
            return json.loads(output.read(32000)) if not returncode else {
                'ok': False, 'note': 'The desktop tool could not complete that action.',
            }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'ok': False, 'note': 'The desktop tool could not verify that action.'}


def _stop_worker(process):
    import psutil

    try:
        for child in psutil.Process(process.pid).children(recursive=True):
            if child.name().casefold() in {'python.exe', 'pythonw.exe'}:
                child.terminate()
    except psutil.Error:
        pass
    if process.poll() is None:
        process.terminate()


def _say(language, english, hindi):
    return hindi if language == 'hi' else english


def _resolve(root, value, folder=False):
    value = re.sub(r'^(?:the |my )?(?:file|folder|फ़ाइल|फाइल|फोल्डर)\s+', '', value, flags=re.I).strip()
    if re.sub(r'^the ', '', _normalize(value)) in {'selected file', 'selected media', 'explorer selection', 'सेलेक्टेड फाइल', 'चुनी हुई फाइल'}:
        try:
            result = subprocess.run(
                [os.sys.executable, '-m', 'hinglish_app.explorer_selection'],
                cwd=root, capture_output=True, timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            paths = json.loads(result.stdout).get('paths', [])
            if result.returncode or len(paths) != 1:
                raise ValueError
            value = paths[0]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'note': 'Select one video or image in File Explorer first.'}
    return _worker('resolve', value, folder=folder)


def _prepare(root, source, target, run, language, active):
    tool = _tool(target, active)
    if not tool:
        return Outcome(_say(language, 'Which Storylens editing tool should I use?', 'स्टोरीलेंस का कौन सा टूल इस्तेमाल करूँ?'), ok=False)
    resolved = _resolve(root, source)
    if not resolved.get('path'):
        return Outcome(_say(language, resolved.get('note', 'Give the exact file or folder path.'),
                            'उस फ़ाइल या फ़ोल्डर का पूरा पाथ बताइए।'), ok=False)
    return Outcome(_say(language, 'I’ll load it into ' + _LABELS[tool] + '.',
                        'मैं इसे ' + _LABELS[tool] + ' में खोलती हूँ।'),
                   {'type': 'prepare_tool', 'tool': tool, 'path': resolved['path'],
                    'path_kind': 'folder' if resolved['folder'] else 'file', 'run': run})


def _draft(value, language):
    if not re.match(r'^(?:draft|compose)\b', value, re.I):
        return None
    match = re.fullmatch(
        r'(?:draft|compose)\s+(?:a\s+)?(gmail|whatsapp)(?:\s+(?:email|message))?\s+to\s+(.+?)'
        r'(?:\s+subject\s+(.+?))?\s+(?:saying|body)\s+(.+)', value, re.I)
    if not match:
        return None
    platform, recipient, subject, body = match.groups()
    data = {'platform': platform.lower(), 'recipient': recipient.strip(), 'subject': subject or '', 'body': body}
    result = _worker('draft', draft=data)
    if result.get('ok'):
        return Outcome(_say(language, 'Your draft is ready to review and send in ' + platform + '.',
                            platform + ' में ड्राफ़्ट तैयार है। आप उसे देखकर भेज सकते हैं।'), minimize=True)
    return Outcome(_say(language, result.get('note', 'The draft could not be verified.'),
                        'ऐप में ड्राफ़्ट की पुष्टि नहीं हो सकी।'), ok=False)


def interpret(root, transcript, language, active, cancelled=None, *, snapshot=()):
    token = _CANCELLED.set(cancelled)
    try:
        return _interpret(root, transcript, language, active, snapshot)
    finally:
        _CANCELLED.reset(token)


_PLATFORM = {
    'instagram': 'instagram', 'insta': 'instagram', 'इंस्टाग्राम': 'instagram',
    'youtube': 'youtube', 'you tube': 'youtube', 'यूट्यूब': 'youtube', 'यू ट्यूब': 'youtube',
    'failed attempts': 'failed',
}


def _setting(value, language, active):
    setting = None
    target = None
    before = None
    if match := re.fullmatch(r'(?:switch|change)(?:\s+(?:the\s+)?(.+?))?\s+from\s+(.+?)\s+to\s+(.+)', value, re.I):
        setting, before, target = match.groups()
    elif match := re.fullmatch(r'(?:set|change|switch)\s+(?:the\s+)?(.+?)\s+to\s+(.+)', value, re.I):
        setting, target = match.groups()
    elif match := re.fullmatch(r'(?:switch|go)\s+to\s+(.+)', value, re.I):
        target = match[1]
    elif match := re.fullmatch(r'(?:show|select|open)\s+(.+?)\s+(?:in|under)\s+(?:the\s+)?scheduled posts', value, re.I):
        target, active = match[1], 'scheduledPosts'
    elif match := re.fullmatch(r'(.+?)\s+से\s+(.+?)\s+(?:पर|पे)\s+(?:स्विच|चेंज|बदल)\s*(?:करो|कर दो|दो)?', value, re.I):
        before, target = match.groups()
    elif match := re.fullmatch(r'(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+)', value, re.I):
        target, setting = match.groups()
    elif match := re.fullmatch(r'(?:turn|switch)\s+(?:the\s+)?(.+?)\s+(on|off)', value, re.I):
        setting, target = match.groups()
    elif match := re.fullmatch(r'(enable|disable)\s+(?:the\s+)?(.+)', value, re.I):
        target, setting = match.groups()
        target = 'on' if target.casefold() == 'enable' else 'off'
    if not target:
        return None
    target = target.strip().strip('"“”')
    setting = setting.strip() if setting else ''
    platform = _PLATFORM.get(_normalize(target))
    if platform and active == 'scheduledPosts' and _normalize(setting) in ('', 'platform', 'platform filter', 'destination'):
        label = {'instagram': 'Instagram', 'youtube': 'YouTube', 'failed': 'Failed attempts'}[platform]
        return Outcome(_say(language, f'Switching Scheduled posts to {label}.',
                            f'शेड्यूल पोस्ट में {label} दिखा रही हूँ।'),
                       {'type': 'schedule_platform', 'platform': platform})
    if not setting and not platform:
        return None
    return Outcome(_say(language, 'I’ll apply that setting.', 'मैं यह सेटिंग बदल रही हूँ।'),
                   {'type': 'set_control', 'label': setting, 'value': platform or target,
                    'from': _PLATFORM.get(_normalize(before), before) if before else ''})


def _button_command(value, language, active, *, opening=False, snapshot=()):
    pattern = _OPEN if opening else r'(?:click(?: on)?|press|tap(?: on)?|hit|expand)'
    match = re.fullmatch(rf'{pattern}\s+(?:(?:the|my)\s+)?(.+)', value, re.I)
    if not match:
        match = re.fullmatch(r'(.+?)(?:\s+(?:बटन|button))?(?:\s+(?:को|पर|पे|ko|par|pe))?\s+(?:दबाओ|दबा दो|क्लिक करो|क्लिक कर दो|टैप करो|dabao|daba do|click karo|tap karo)', value, re.I)
    if not match:
        return None
    label = match[1]
    tool = ''
    if scope := re.fullmatch(r'(.+?)\s+(?:in|under|inside|on)\s+(?:the\s+)?(.+)', label, re.I):
        tool = _tool(scope[2], active)
        if tool:
            label = scope[1]
    if not tool and (scope := re.fullmatch(r'(.+?)\s+(?:में|mein|me)\s+(.+)', label, re.I)):
        tool = _tool(scope[1], active)
        if tool:
            label = scope[2]
    label = re.sub(r'\s+(?:button|बटन)$', '', label, flags=re.I).strip(' "“”')
    if not label or len(label) > 160:
        return None
    if opening:
        from .support_call_controls import toolbar_button_name
        label, tool = toolbar_button_name(label, tool, active, snapshot)
        if not label:
            return None
    return Outcome(_say(language, f'Pressed {label}.', f'{label} दबा दिया।'),
                   {'type': 'click_button', 'label': label, 'tool': tool})


def _interpret(root, transcript, language, active, snapshot):
    value = _strip_command(transcript)
    if not value or _NEGATIVE.search(value):
        return None
    if button := _button_command(value, language, active):
        return button
    if setting := _setting(value, language, active):
        return setting
    if _RUN_CURRENT.fullmatch(value):
        return Outcome(_say(language, 'Running the source we selected.', 'चुनी हुई फ़ाइल पर टूल चला रही हूँ।'),
                       {'type': 'run_prepared'})
    if match := re.fullmatch(r'(?:load|add|put|import|use|select)\s+(.+)', value, re.I):
        if active in FEATURES and not _PREPARE.fullmatch(value):
            return _prepare(root, match[1], 'this tool', False, language, active)
    if match := re.fullmatch(r'(.+?)(?:\s+को)?\s+(?:डालो|डाल दो|चुनो|चुन लो|लोड करो|इम्पोर्ट करो)', value, re.I):
        if active in FEATURES:
            return _prepare(root, match[1], 'this tool', False, language, active)
    draft = _draft(value, language)
    if draft:
        return draft
    if match := _PREPARE.fullmatch(value) or _HI_PREPARE.fullmatch(value):
        return _prepare(root, match[1], match[2], bool(match[3]), language, active)
    if match := re.fullmatch(r'(?:run|generate|start)\s+(.+)', value, re.I):
        tool = _tool(match[1], active)
        if tool:
            return Outcome(_say(language, 'Running ' + _LABELS[tool] + '.', _LABELS[tool] + ' चला रही हूँ।'),
                           {'type': 'run_prepared', 'tool': tool})
    if match := _GENERATE.fullmatch(value):
        if _tool(match[1], active):
            return _prepare(root, match[2], match[1], True, language, active)
    if match := re.fullmatch(r'(?:find|search for)\s+(?:(?:the|my|a)\s+)?(?:file\s+(.+)|(.+\.[a-z0-9]{2,6}))', value, re.I):
        names = _worker('search', match[1] or match[2]).get('names', [])
        if names:
            return Outcome(_say(language, 'I found ' + ', '.join(names) + '.', 'मुझे ये फ़ाइलें मिलीं: ' + ', '.join(names) + '।'))
        return Outcome(_say(language, 'I didn’t find a matching file in the configured folders.', 'कॉन्फ़िगर किए गए फ़ोल्डरों में यह फ़ाइल नहीं मिली।'), ok=False)
    if re.fullmatch(r'(?:list|show)(?: me)? (?:my |the )?(?:open windows|running apps)', value, re.I):
        names = _worker('windows').get('names', [])
        return Outcome(_say(language, 'Open windows include ' + ', '.join(names) if names else 'I couldn’t list the open windows.',
                            'इनकी विंडो खुली हैं: ' + ', '.join(names) if names else 'खुली विंडो की सूची नहीं मिली।'))
    if match := re.fullmatch(r'(?:focus|bring forward)\s+(.+)', value, re.I):
        return _desktop('focus', match[1], language)
    match = re.fullmatch(rf'{_OPEN}\s+(.+)', value, re.I)
    if not match:
        match = re.fullmatch(rf'(.+?)\s+(?:(?:ko|को)\s+)?{_OPEN}(?:\s+(?:karo|kar do|करो|कर दो|दो))?', value, re.I)
    if not match:
        # ASR can insert commas inside Hindi commands: "Auto Captions, kholo, do".
        spoken = re.sub(r'[,!?।]+', ' ', value)
        spoken = re.sub(r'\s+', ' ', spoken).strip()
        candidate = re.fullmatch(rf'(.+?)\s+(?:(?:ko|को)\s+)?{_OPEN}', spoken, re.I)
        if candidate and (_tool(candidate[1], active) or _normalize(candidate[1]) in _APP_NAMES):
            match = candidate
    if not match:
        return None
    target = re.sub(r'^(?:the|my|मेरा|मेरी|मुझे)\s+', '', match[1].strip(), flags=re.I)
    target = re.sub(r'\s+(?:software|editor app|application|app|ऐप|सॉफ्टवेयर|सॉफ़्टवेयर)$', '', target, flags=re.I)
    target = target.strip(' "“”')
    tool = _tool(target, active)
    if tool:
        if tool == 'preparePost':
            action = {'type': 'open_publishing'}
        elif tool == 'scheduledPosts':
            action = {'type': 'open_schedule'}
        else:
            action = {'type': 'open_tool', 'tool': tool}
        return Outcome(_say(language, 'Opening ' + _LABELS[tool] + '.',
                            _LABELS[tool] + ' खोलती हूँ।'), action)
    if button := _button_command(value, language, active, opening=True, snapshot=snapshot):
        return button
    name = _normalize(target)
    if name in _APP_NAMES:
        return _desktop('open', _APP_NAMES[name], language)
    named_drive = {'डी ड्राइव':'D drive','सी ड्राइव':'C drive','ई ड्राइव':'E drive'}
    if name in named_drive:
        return _desktop('path', named_drive[name], language, folder=True)
    if name in ('result', 'view result', 'export', 'export options'):
        return Outcome(_say(language, 'Opening ' + target + '.', target + ' खोलती हूँ।'),
                       {'type': 'navigate', 'target': 'export' if 'export' in name else 'result'})
    if match_excel := re.fullmatch(r'(.+\.(?:xlsx|csv|tsv))["”]?\s+(?:in|with)\s+(?:microsoft\s+)?excel', target, re.I):
        return _desktop('path', match_excel[1].strip(' "“”'), language, app='excel')
    named_folder = re.fullmatch(r'(.+?)\s+(?:वाला\s+)?(?:folder|फोल्डर|फ़ोल्डर)', target, re.I)
    if named_folder:
        return _desktop('path', named_folder[1], language, folder=True)
    if re.match(r'^(?:folder|file|फ़ाइल|फाइल|फोल्डर|फ़ोल्डर)\s+', target, re.I) or re.match(r'^[a-z]:[\\/]', target, re.I) or re.fullmatch(r'[a-z] (?:drive|ड्राइव)', target, re.I):
        prefix = re.match(r'^(folder|फोल्डर|फ़ोल्डर)\s+', target, re.I)
        path = re.sub(r'^(?:folder|file|फ़ाइल|फाइल|फोल्डर|फ़ोल्डर)\s+', '', target, flags=re.I)
        return _desktop('path', path.strip(' "“”'), language,
                        folder=bool(prefix and prefix[1].casefold() in {'folder', 'फोल्डर', 'फ़ोल्डर'}))
    if re.fullmatch(r'[^/\\:*?"<>|]+\.(?:pdf|docx|xlsx|pptx|txt|md|csv|tsv|json|png|jpe?g|webp|mp[34]|wav|mkv|mov)', target, re.I):
        return _desktop('path', target, language)
    if re.search(r'\b(?:and|then)\b|और', target, re.I):
        return None
    return _desktop('open', _APP_NAMES.get(name, name), language)


def _desktop(kind, target, language, **params):
    result = _worker(kind, target, **params)
    if result.get('ok'):
        name = result.get('name') or target
        return Outcome(_say(language, 'Opened ' + name + '.', name + ' खोल दिया।'), minimize=True)
    return Outcome(_say(language, result.get('note') or 'I couldn’t open ' + target + '.',
                        target + ' नहीं खुल पाया।'), ok=False)
