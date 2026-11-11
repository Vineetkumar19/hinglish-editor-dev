"""Source and live UI evidence for Cortana's Storylens control guide."""
import base64
from functools import lru_cache
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from .support_call_knowledge import FEATURES, _normalize

_STATIC = Path(__file__).with_name('static')
_WORKFLOW = Path('D:/Workflow_Automation')
_CONTROL_QUERY = re.compile(r'\b(?:buttons?|controls?|settings?|what does|how do i|what is|where is|kaise|kya karta)\b|बटन|किस काम|सेटिंग|क्या करता|कहाँ|कैसे', re.I)

# Names are taken from the actual rendered controls or their UI handlers.
# The generic rules are for repeated labels whose meaning is scoped by the tool.
_DESCRIPTIONS = {
    'apply custom timing': 'Uses the current intro duration and number of cuts to select a matching saved timing for the preview.',
    'play intro': 'Plays the selected intro draft with its current timing.',
    'stop': 'Stops the current preview or work in this panel. The exact target is the active panel.',
    'review saved candidates': 'Reopens the selected Cinematic Footage extraction for review.',
    'resume interrupted extraction': 'Continues the selected interrupted Cinematic Footage extraction.',
    'extract shots': 'Scans the selected videos or folder and saves candidate shots for review.',
    'find matches': 'Looks for visually similar footage pairs suitable for a match cut.',
    'find moments': 'Scans the selected footage or saved source for slow-motion candidates.',
    'save draft changes': 'Saves the changes to the current draft for later review and export.',
    'download after effects pre comps': 'Exports the current draft as editable After Effects pre-comps.',
    'download drx': 'Downloads the saved DaVinci Resolve grade as a DRX file.',
    'apply to duplicate timeline': 'Applies the native editable grade to a duplicate Resolve timeline.',
    'import test recording': 'Opens the Call QA importer for a consented test recording.',
    'export anonymized': 'Downloads the Call QA report with identifying fields removed.',
    'save anonymized json locally': 'Saves the anonymized Call QA report to a local JSON file.',
    'save your voice': 'Opens the flow to save a reusable voice sample for Voice Clone.',
    'scheduled posts': 'Opens the current publishing queue and its platform and channel filters.',
    'youtube': 'In Scheduled posts, filters the list to YouTube. In other tools, the selected setting determines its meaning.',
    'instagram': 'In Scheduled posts, filters the list to Instagram. In other tools, the selected setting determines its meaning.',
    'failed attempts': 'Filters Scheduled posts to entries whose publication or operation needs attention.',
    'save changes': 'Saves the edits for the selected item. In Scheduled posts, this updates the selected post through its existing workflow.',
    'cancel schedule': 'Starts cancellation of the schedule for the selected post through the existing review flow.',
    'publish now': 'Requests immediate publication for the selected scheduled post.',
    'post now': 'Submits the current reviewed video or clips through the publishing workflow.',
    'schedule': 'Submits the reviewed video or clips for their scheduled release.',
    'connections': 'Opens the publishing account connection panel for the selected creator profile.',
    'connect youtube': 'Starts Google sign-in for the selected creator profile’s YouTube connection.',
    'connect instagram': 'Opens the instructions to pair Storylens with the signed-in Chrome Instagram connection.',
    'close scheduled posts': 'Closes the scheduled posts review panel.',
    'refresh feeds now': 'Runs the configured feed collection for the current desk.',
    'run gpt once now': 'Requests a one-off research pass using the current desk’s configured scope.',
    'save research settings': 'Saves the desk’s research schedule and selected sources.',
    'collect posts': 'Updates the current event focus and requests fresh candidates.',
    'export selected': 'Exports the desk’s currently selected sources and available images.',
    'to review': 'Shows candidates still waiting for a review decision.',
    'selected': 'Shows candidates you marked to keep.',
    'skipped': 'Shows candidates you skipped so you can revisit them.',
    'keep': 'Marks the current candidate as selected.',
    'skip': 'Moves the current candidate out of the review queue.',
    'restore': 'Returns the current candidate to its earlier review queue.',
    'save image': 'Saves the image associated with the selected candidate.',
    'reconnect agent suite': 'Reconnects the existing Agent Suite service and reloads its social-account status; existing work and review queues are preserved.',
    'check social accounts': 'Checks the connected social identities shown in AI Agents.',
    'check comments': 'Requests a comment check for the selected account.',
    'refresh inbox': 'Updates the agent inbox list.',
    'connect replies': 'Starts the selected account’s reply-permission connection flow.',
    'clear': 'Clears the current screen fields. Check the named control and its tooltip for the exact scope.',
    'view result': 'Shows the finished result of the active editing tool.',
    'export': 'Opens the export controls for the active tool’s result.',
    'output settings': 'Expands the active tool’s output options, such as aspect ratio and processing device.',
    'activity': 'Expands the current job log so you can see what the tool is doing.',
    'open folder': 'Opens the result’s folder in File Explorer.',
    'call': 'Starts a Cortana AI voice call and asks for microphone access if needed.',
    'voice assistant': 'Starts a Cortana AI voice call and asks for microphone access if needed.',
    'minimize call': 'Docks the voice call while keeping the session active.',
    'restore cortana ai call': 'Expands the docked call panel.',
    'pause call': 'Pauses voice capture and playback.',
    'resume call': 'Resumes the paused voice session.',
    'end call': 'Ends the voice session and releases its microphone stream.',
    'try again': 'Retries starting the call after a connection or voice engine error.',
    'resize call panel': 'Drag this handle or use the arrow keys to resize the call panel.',
    'choose videos': 'Opens the file picker to select one or more input videos.',
    'choose folder': 'Opens a folder picker for the current tool.',
    'close': 'Dismisses the current dialog or panel.',
    'reset': 'Restores the defaults or clears the current selection in the active panel.',
}

_EXTRA = {
    'scheduledPosts': ('Scheduled posts', 'Cricket', 'Gaming', 'YouTube', 'Instagram', 'Failed attempts',
                       'Save changes', 'Cancel schedule', 'Publish now', 'Delete', 'Close scheduled posts'),
    'finance': ('Open Pocket Tracker', 'Open Finance Tracker'),
    'aiAgents': ('Check social accounts', 'Check comments', 'Refresh inbox', 'Connect replies', 'Reconnect Agent Suite'),
    'cricketDesk': ('Keep', 'Skip', 'Restore', 'Save image', 'View source'),
    'gamingDesk': ('Keep', 'Skip', 'Restore', 'Save image', 'View source'),
    'storylensCall': ('Call', 'Minimize call', 'Restore Cortana AI call', 'Pause', 'Resume', 'End call', 'Try again', 'Resize call panel'),
    'assistant': ('Attach', 'Speak your editing request', 'Send', 'Ask the editor', 'Start a new chat'),
    'chatHistory': ('Chats', 'New chat', 'Read full conversation'),
}
_OTHER = {
    'preparePost': 'prepare-post.html', 'activation': 'activation.html',
    'importantCaptions': 'important-captions.html', 'aiAgents': 'ai-agents.html', 'finance': 'finance.html',
    'analytics': 'creator-analytics.html', 'support': 'index.html',
    'assistant': 'index.html', 'storylensCall': 'call-qa.html', 'results': 'index.html',
    'workflow': 'workflow.html', 'scheduledPosts': 'prepare-post.html',
    'chatHistory': 'index.html', 'profiles': 'index.html', 'chromePublisher': 'chrome.html',
    'stockBrowser': 'stock-browser.html', 'documentaryIntro': 'documentary-intro.html',
    'nativeCuration': 'native-curation.html', 'cinematicReels': 'cinematic.html',
}


class _Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if (tag in ('button', 'summary') or attrs.get('role') in ('button', 'tab')
                or tag == 'a' and (attrs.get('id') or 'action' in attrs.get('class', '') or 'data-voice-label' in attrs)):
            self.current = (tag, attrs, [])
        elif tag == 'input' and attrs.get('type') in ('button', 'submit', 'reset'):
            name = attrs.get('aria-label') or attrs.get('title') or attrs.get('value')
            if name:
                self.items.append((name, attrs.get('title', ''), attrs.get('onclick', '')))

    def handle_data(self, data):
        if self.current:
            self.current[2].append(data)

    def handle_endtag(self, tag):
        if self.current and self.current[0] == tag:
            _, attrs, parts = self.current
            name = attrs.get('data-voice-label') or attrs.get('aria-label') or ' '.join(' '.join(parts).split()) or attrs.get('title')
            name = {
                'run': 'Clean my videos' if _normalize(name) == 'clean my videos run' else name,
                'pickMusic': 'Change music folder',
                'pickSfx': 'Change effects folder',
                'pick-source': 'Choose file',
            }.get(attrs.get('id'), name)
            if attrs.get('data-grade-mode'):
                name = 'Color Grade 1' if attrs['data-grade-mode'] == 'realfilm' else 'Color Grade 2'
            if attrs.get('data-style'):
                attrs['onclick'] = 'caption-style'
                match = re.search(r'Caption \d+\s*-\s*.+|Typography \d+|Kinetic Documentary|Documentary Outline|Documentary Echo|Cinematic Script Mix|Cinematic Clean Reveal', name)
                if match:
                    name = match[0]
            if name == 'Output settings Optional':
                name = 'Output settings'
            if 'mode' in attrs.get('class', '').split() and attrs.get('data-mode') in FEATURES:
                name = FEATURES[attrs['data-mode']][0]
            if name and _normalize(name):
                self.items.append((name, attrs.get('title', ''), attrs.get('onclick', '')))
            self.current = None


@lru_cache(maxsize=40)
def _read(path):
    parser = _Controls()
    if path.is_file():
        parser.feed(path.read_text(encoding='utf-8-sig', errors='replace'))
    return tuple(parser.items)


@lru_cache(maxsize=1)
def _routes():
    source = (_STATIC/'app.js').read_text(encoding='utf-8')
    line = next((line for line in source.splitlines() if 'const routes=' in line), '')
    return dict(re.findall(r'"([A-Za-z]+)"\s*:\s*"([^"?]+\.html)(?:\?[^"]*)?"', line))


@lru_cache(maxsize=1)
def _catalogue():
    result = {}
    section = None
    for line in Path(__file__).with_name('support_call_button_catalog.txt').read_text(encoding='utf-8').splitlines():
        if line.startswith('['):
            section = result.setdefault(line[1:-1], {})
        elif ' | ' in line and section is not None:
            label, purpose = line.split(' | ', 1)
            section[_normalize(label)] = (label, purpose)
    return result


def _tool_entries(tool):
    catalogue = _catalogue()
    base = catalogue.get('cricketDesk', {}) if tool == 'gamingDesk' else {}
    return {**base, **catalogue.get(tool, {})}


@lru_cache(maxsize=80)
def controls(tool):
    if tool not in FEATURES:
        return ()
    if tool == 'cricketDesk':
        path = _WORKFLOW/'cricket-meme-inbox/index.html'
    elif tool == 'gamingDesk':
        path = _WORKFLOW/'gaming-meme-inbox/index.html'
    else:
        path = _STATIC/(_OTHER.get(tool) or _routes().get(tool) or 'index.html')
    rows = [(label, '', '') for label, _ in _tool_entries(tool).values()]
    keys = {_normalize(label) for label, _, _ in rows}
    common = _catalogue()['common']
    source_rows = () if tool in ('storylensCall','scheduledPosts') else _read_scoped(path)
    for label, title, handler, scope in source_rows:
        key = _normalize(label)
        if key in keys:
            continue
        if path.name in ('index.html', 'editor-panel.html') and scope != tool and key not in common and not (
                tool == 'captions' and handler == 'caption-style'):
            # Both HTML files declare hidden panels for unrelated features.
            continue
        rows.append((label, title, handler))
        keys.add(key)
    for label in _EXTRA.get(tool, ()):
        if _normalize(label) not in keys:
            rows.append((label, '', ''))
    return tuple(rows)


def decode_snapshot(value):
    try:
        if not value or len(value) > 4096:
            return ()
        rows = json.loads(base64.b64decode(value, validate=True))
    except (ValueError, UnicodeError):
        return ()
    if not isinstance(rows, list):
        return ()
    rows = [row for row in rows[:100] if isinstance(row, list) and len(row) in (2, 3)
            and isinstance(row[0], str) and isinstance(row[1], bool)]
    return tuple((row[0][:90], row[1], row[2] if len(row) == 3 and isinstance(row[2], str) else '')
                 for row in rows)


def _description(name, title, handler, tool):
    key = _normalize(name)
    scoped = {
        ('templateAligner','template fonts'): 'Expands the connected After Effects template font report, including missing fonts and substitutions.',
        ('templateAligner','collapse folders'): 'Closes Project-panel folders through the connected After Effects template folder cleanup action; keeps the timeline.',
        ('templateAligner','check fonts'): 'Checks fonts used by the connected After Effects templates and lists missing fonts while retaining original font choices.',
        ('presetLibrary','paste'): 'Places the copied media into the selected preset layer footage slot through the native editor bridge.',
        ('presetLibrary','undo'): 'Reverts the last tracked media paste into a preset layer.',
    }
    if (tool,key) in scoped: return scoped[(tool,key)]
    if entry := _tool_entries(tool).get(key):
        return entry[1]
    if entry := _catalogue()['common'].get(key):
        return entry[1]
    if key in _DESCRIPTIONS:
        return _DESCRIPTIONS[key]
    if entry := _catalogue()['dynamic'].get(_normalize(handler)):
        return entry[1]
    if title and _normalize(title) != key:
        return title
    if handler and 'openSettings' in handler:
        return 'Opens this desk’s research settings.'
    for feature, (label, _, _) in FEATURES.items():
        if key == _normalize(label) and feature != tool:
            return f'Opens the {label} feature.'
    return ''


def control_guidance(question, active, snapshot=()):
    query = ' ' + _normalize(question) + ' '
    candidates = [(len(name), key) for key, (label, aliases, _) in FEATURES.items()
                  for name in map(_normalize, [label, *aliases.split('|')])
                  if len(name) > 3 and ' ' + name + ' ' in query]
    tool = max(candidates, default=(0, active), key=lambda item: item[0])[1]
    rows = controls(tool)
    live = {_normalize(row[0]): (row[0], row[1], row[2] if len(row) == 3 else '')
            for row in snapshot} if tool == active else {}
    found = {}
    for name, title, handler in rows:
        key = _normalize(name)
        if key and ' ' + key + ' ' in query:
            purpose = _description(name, title, handler, tool)
            if key not in found or purpose and not found[key][1]:
                found[key] = (name, purpose)
    for key, (name, enabled, family) in live.items():
        if key and ' ' + key + ' ' in query:
            known = found.get(key, (name, ''))[1]
            found[key] = (name, known or _description(name, '', family, tool))
    if not found:
        if not _CONTROL_QUERY.search(question):
            return ''
        names = [label + ('' if enabled else ' [disabled]') for label, enabled, _ in live.values()]
        if not names:
            names = list(dict.fromkeys(name for name, _, _ in rows))
        return 'Button labels on the named screen: ' + ', '.join(names[:42])
    ordered = []
    for key, entry in sorted(found.items(), key=lambda item: -len(item[0])):
        if not any(f' {key} ' in f' {longer} ' for longer, _ in ordered):
            ordered.append((key, entry))
    lines = []
    for key, (name, purpose) in ordered[:4]:
        state = (' Enabled in the current view.' if live[key][1] else ' Disabled in the current view.') if key in live else ''
        lines.append(f'{name}: {purpose or "The label is verified; its specific effect is not documented here."}{state}')
    return '\n'.join(lines)


# Narrow label equivalences, never substring/fuzzy matching of destructive actions.
_LABEL_WORDS = {
    'videos': 'video', 'files': 'file', 'folders': 'folder', 'images': 'image',
    'photos': 'photo', 'templates': 'template', 'captions': 'caption',
}
_LABEL_ALIASES = {
    'चूज़ वीडियो': 'choose video', 'चूज वीडियो': 'choose video',
    'वीडियो चुनो': 'choose video', 'वीडियो चुनें': 'choose video',
    'video chuno': 'choose video', 'select video': 'choose video', 'pick video': 'choose video',
    'चूज़ फोल्डर': 'choose folder', 'चूज फोल्डर': 'choose folder',
    'फोल्डर चुनो': 'choose folder', 'फ़ोल्डर चुनो': 'choose folder', 'folder chuno': 'choose folder',
    'select folder': 'choose folder', 'pick folder': 'choose folder',
    'आउटपुट सेटिंग्स': 'output settings', 'आउटपुट सेटिंग': 'output settings',
    'हिस्ट्री': 'history', 'प्ले': 'play', 'स्टॉप': 'stop',
    'सेव चेंजेस': 'save changes', 'एक्सपोर्ट': 'export',
    'pocket tracker': 'open pocket tracker', 'finance tracker': 'open finance tracker',
    'financial tracker': 'open finance tracker', 'comment replies': 'open replies',
    'all workflows': 'open workflows', 'three dots': 'developer tools',
    'scheduled post': 'scheduled posts', 'profile settings': 'profile',
    'open ai agents': 'ai agents', 'publish studio': 'publishing studio',
    'maximize call': 'expand call to fill screen', 'maximize voice assistant': 'expand call to fill screen',
    'search all conversations': 'search all chats',
    'search chats': 'search all chats',
}

def button_name_key(value):
    key = _normalize(value)
    key = re.sub(r'^(?:the|यह|ये)\s+', '', key)
    key = re.sub(r'\s+(?:button|बटन)$', '', key)
    key = ' '.join(_LABEL_WORDS.get(word, word) for word in key.split())
    return _LABEL_ALIASES.get(key, key)

def match_button_name(value, names):
    """Prefer an exact live label, then one unambiguous spoken equivalence."""
    names = list(dict.fromkeys(name for name in names if isinstance(name, str)))
    exact = [name for name in names if _normalize(name) == _normalize(value)]
    if exact:
        return exact[0] if len(exact) == 1 else ''
    equivalent = [name for name in names if button_name_key(name) == button_name_key(value)]
    return equivalent[0] if len(equivalent) == 1 else ''

def resolve_button_name(value, tool, active, snapshot=()):
    if not tool or tool == active:
        match = match_button_name(value, [row[0] for row in snapshot])
        if match:
            return match
    return match_button_name(value, [name for name, _, _ in controls(tool or active)])


_HEADER_WORKSPACES = frozenset({
    'chatHistory', 'support', 'preparePost', 'finance', 'analytics', 'aiAgents',
    'storylensCall', 'assistant', 'scheduledPosts', 'profiles',
})

def toolbar_button_name(value, tool='', active='', snapshot=()):
    if tool and tool not in _HEADER_WORKSPACES:
        return '', ''
    if not tool or tool == active:
        label = match_button_name(value, [row[0] for row in snapshot])
        if label:
            return label, tool
    if tool or active in _HEADER_WORKSPACES:
        label = resolve_button_name(value, tool, active)
        if label:
            return label, tool
    # Distinctive names are discoverable from the editor. Generic labels such
    # as Refresh or Open still require an explicit workspace.
    top = match_button_name(value, [FEATURES[key][0] for key in _HEADER_WORKSPACES])
    if top and not tool:
        return top, ''
    unique_names = {
        'finance': ('Open Pocket Tracker', 'Open Finance Tracker'),
        'aiAgents': (*_AGENT_SECTIONS, 'Open replies', 'Demand research', 'Open workflows', 'Developer tools'),
        'storylensCall': ('Expand call to fill screen', 'Restore call size', 'Close voice assistant',
                          'Minimize call', 'Restore Cortana AI call'),
    }
    for surface, names in unique_names.items():
        if tool and tool != surface:
            continue
        name = match_button_name(value, names)
        if name:
            return name, surface
    return '', ''


def toolbar_help(question, active='', snapshot=()):
    query = _normalize(question)
    if not re.match(r'^(?:what|which|how|where|tell me|explain|describe|list)\b', query):
        return ''
    from .support_call_actions import _tool
    scope = re.search(r'\b(?:in|under|inside|on)\s+(.+)$', query)
    explicit = _tool(scope[1], '') if scope else ''
    if explicit and explicit not in _HEADER_WORKSPACES:
        return ''
    tool = explicit or active
    if tool not in _HEADER_WORKSPACES:
        return ''
    if scope and explicit:
        query = query[:scope.start()].strip()
    entries = {**_tool_entries(tool)}
    for name, title, handler in controls(tool):
        entries.setdefault(_normalize(name), (name, _description(name, title, handler, tool)))
    if tool == active:
        for name, _, family in snapshot:
            entries.setdefault(_normalize(name), (name, _description(name, '', family, tool)))
    named = [entry for key, entry in entries.items() if len(key) >= 3 and _phrase_in(key, query) and entry[1]]
    if named:
        return max(named, key=lambda entry: len(entry[0]))[1]
    return ''


# Dropdowns are read from actual HTML and the current browser snapshot, not
# invented by a model. Cached source parsing keeps ordinary commands CPU-only.
_FIELD_CLASSES = {
    'thumbnail-field': 'thumbnail', 'gaming-field': 'gaming', 'zoom-field': 'zoom',
    'eye-field': 'eyecontact', 'aivideo-field': 'aivideo', 'motion-field': 'motion',
    'shorts-field': 'shorts', 'sound-field': 'sound', 'visuals-field': 'visuals',
    'broll-field': 'broll', 'caption-field': 'captions', 'script-field': 'script',
}
_VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class _Selects(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.rows, self.labels = [], [], {}
        self.label = self.current = self.option = None

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'label':
            self.label = {'for': attrs.get('for', ''), 'text': [], 'rows': []}
        if tag == 'select':
            ancestors = [row[1] for row in self.stack] + [attrs]
            scope = _scope(ancestors)
            label = attrs.get('aria-label') or self.labels.get(attrs.get('id'), '')
            if not label and self.label:
                label = ' '.join(' '.join(self.label['text']).split())
            self.current = {'id': attrs.get('id', ''), 'label': label,
                            'options': [], 'disabled': 'disabled' in attrs,
                            '_tool': scope, 'type': 'select'}
            if self.label:
                self.label['rows'].append(self.current)
        elif tag == 'option' and self.current is not None:
            self.option = {'value': attrs.get('value'), 'label': '',
                           'disabled': 'disabled' in attrs, '_text': []}
        if tag not in _VOID:
            self.stack.append((tag, attrs))

    def handle_data(self, data):
        if self.option is not None:
            self.option['_text'].append(data)
        elif self.label is not None:
            self.label['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'option' and self.option is not None:
            option = self.option
            option['label'] = ' '.join(' '.join(option.pop('_text')).split())
            if option['value'] is None:
                option['value'] = option['label']
            self.current['options'].append(option)
            self.option = None
        elif tag == 'select' and self.current is not None:
            self.rows.append(self.current)
            self.current = None
        elif tag == 'label' and self.label is not None:
            label = ' '.join(' '.join(self.label['text']).split())
            if self.label['for']:
                self.labels[self.label['for']] = label
            for row in self.label['rows']:
                row['label'] = row['label'] or label
            self.label = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


_SCOPE_IDS = {
    'brollSettings':'broll', 'autoCaptionPanel':'captions',
    'templateAlinerSection':'templateAligner', 'templateAlinerSettings':'templateAligner',
    'templateImportSection':'templateImport', 'templateTextSection':'templateText',
    'copyPasteSection':'copyPaste', 'imageDownloadSection':'imageDownload',
    'animationPresetSection':'animationPresets', 'effectsSection':'textEffects',
    'presetSection':'presetLibrary', 'effectsTemplatesSection':'presetLibrary',
    'captionSettings':'nativeCaptions', 'soundSettings':'sound', 'savedSoundControls':'sound',
    'savedBrollControls':'broll', 'savedVisualControls':'visuals',
    'storylens-call-panel':'storylensCall', 'sharedSettings':'@native-shared',
    'channelPreferences':'profiles', 'channelCards':'profiles',
    'assistantForm':'assistant', 'chatHistorySearch':'chatHistory',
}


def _scope(ancestors):
    scope = ''
    for attrs in ancestors:
        current = _SCOPE_IDS.get(attrs.get('id'))
        for cls, tool in _FIELD_CLASSES.items():
            if cls in attrs.get('class', '').split(): current = tool
        if current: scope = current
    return scope


class _ScopedControls(_Controls):
    def __init__(self):
        super().__init__()
        self.stack, self.scoped = [], []
        self.current_scope = ''

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        before = len(self.items)
        super().handle_starttag(tag, pairs)
        if self.current is not None and self.current[0] == tag:
            self.current_scope = _scope([a for _, a in self.stack] + [attrs])
        if len(self.items) > before:
            self.scoped.extend((*row, _scope([a for _, a in self.stack] + [attrs])) for row in self.items[before:])
        if tag not in _VOID: self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        before = len(self.items)
        super().handle_endtag(tag)
        if len(self.items) > before:
            self.scoped.extend((*row, self.current_scope) for row in self.items[before:])
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


@lru_cache(maxsize=80)
def _read_scoped(path):
    parser = _ScopedControls()
    if path.is_file(): parser.feed(path.read_text(encoding='utf-8-sig', errors='replace'))
    return tuple(parser.scoped)


class _Fields(_Selects):
    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        super().handle_starttag(tag, pairs)
        field_type = attrs.get('type', 'text') if tag == 'input' else tag
        if tag not in ('input','textarea') or field_type in ('hidden','password','button','submit','reset'):
            return
        identity = attrs.get('id','')
        label = attrs.get('aria-label') or self.labels.get(identity, '')
        if not label and self.label:
            label = ' '.join(' '.join(self.label['text']).split())
        row = {'id':identity, 'label':label, 'type':field_type,
               'disabled':'disabled' in attrs, 'options':[],
               '_tool':_scope([a for _,a in self.stack] + [attrs])}
        for key in ('min','max','step','maxlength','accept'):
            if key in attrs: row[key] = attrs[key]
        self.rows.append(row)
        if self.label: self.label['rows'].append(row)


def _surface_path(tool):
    if tool in ('cricketDesk','gamingDesk'):
        return _WORKFLOW / ('cricket-meme-inbox' if tool == 'cricketDesk' else 'gaming-meme-inbox') / 'index.html'
    return _STATIC / (_OTHER.get(tool) or _routes().get(tool) or 'index.html')


@lru_cache(maxsize=80)
def form_fields(tool):
    """Source-declared fields; an empty dropdown denotes runtime options, not absence."""
    if tool not in FEATURES or tool in ('storylensCall','scheduledPosts'): return ()
    path = _surface_path(tool)
    if not path.is_file(): return ()
    parser = _Fields()
    parser.feed(path.read_text(encoding='utf-8-sig', errors='replace'))
    result=[]
    for row in parser.rows:
        scope = row['_tool']
        if path.name == 'index.html':
            if scope != tool and not (not scope and row['id'] in ('format','device','pacing','inputPath')):
                continue
        elif path.name == 'editor-panel.html':
            if scope != tool and not (scope == '@native-shared' and tool in ('nativeCaptions','textEffects','templateText')):
                continue
        if row['id'] and row['label']:
            clean = {key:value for key,value in row.items() if not key.startswith('_')}
            if row['type']=='select':
                clean['dynamic'] = not any(option['value'] for option in row['options'])
            result.append(clean)
    return tuple(result)


@lru_cache(maxsize=80)
def select_fields(tool):
    return tuple(row for row in form_fields(tool) if row['type']=='select')


def decode_fields(value):
    """Bound untrusted live UI metadata; never accept free-text input values."""
    try:
        if not value or len(value) > 12000:
            return ()
        raw = json.loads(base64.b64decode(value, validate=True))
    except (ValueError, UnicodeError):
        return ()
    if not isinstance(raw, list):
        return ()
    rows = []
    for item in raw[:40]:
        if not isinstance(item, dict) or not isinstance(item.get('label'), str) or not isinstance(item.get('options'), list):
            continue
        options = [{'value': option['value'][:240], 'label': option['label'][:160],
                    'disabled': option.get('disabled') is True}
                   for option in item['options'][:80]
                   if isinstance(option, dict) and isinstance(option.get('value'), str)
                   and isinstance(option.get('label'), str)]
        rows.append({'id': str(item.get('id', ''))[:160], 'label': item['label'][:160],
                     'disabled': item.get('disabled') is True, 'options': options})
    return tuple(rows)


def _option_key(value):
    text = _normalize(str(value).replace('।', ' ').replace('॥', ' '))
    # Known product spelling variants, not approximate matching of arbitrary values.
    text = re.sub(r'\bhyper\s*frames?\b|हाइपर\s*फ्रेम्स?', 'hyperframes', text)
    return text


def _phrase_in(value, text):
    return bool(value and (' ' + value + ' ') in (' ' + text + ' '))


def option_command(text, active_tool='', fields=()):
    """Return one grounded dropdown action, or None for questions/ambiguity."""
    from .support_call_knowledge import _match
    query = _option_key(text)
    if re.search(r"\b(?:don t|do not|never|not|nahi|nahin|mat|what|why|how|explain|if|suppose)\b|मत|नहीं|क्या है|कैसे|क्यों", query):
        return None
    if re.search(r"['\u201c\u201d\u0022]", str(text)):
        return None
    command = bool(re.search(
        r'\b(?:set|select|choose|use|switch|change|make|pick|kar do|kar de|karo|cardo|chuno|laga do)\b'
        r'|(?:^|\s)कर\s*(?:दो|दे|दीजिए)(?=\s|$)|करो|चुनो|चुन लो|सेलेक्ट|लगाओ|लगा दो', query))
    named = _match(' ' + _normalize(text) + ' ')
    if len(named) > 1:
        return None
    tool = named[0] if named else active_tool
    if tool not in FEATURES:
        return None
    rows = list(select_fields(tool))
    if tool == active_tool and fields:
        # A live field wins, including a disabled control or removed options.
        live_ids = {row.get('id') for row in fields}
        live_labels = {_normalize(row.get('label', '')) for row in fields}
        rows = [row for row in rows if row.get('id') not in live_ids
                and _normalize(row.get('label', '')) not in live_labels] + list(fields)
    explicit = [row for row in rows if _phrase_in(_option_key(row.get('label', '')), query)]
    if explicit:
        rows = explicit
    hits = []
    for row in rows:
        if row.get('disabled'):
            continue
        for option in row.get('options', ()):
            if option.get('disabled'):
                continue
            keys = {_option_key(option.get('label', '')), _option_key(option.get('value', ''))} - {''}
            match = any(_phrase_in(key, query) for key in keys)
            bare = query in keys
            if match and (command or bare):
                hits.append((row, option))
    unique = {(row.get('id'), option.get('value')): (row, option) for row, option in hits}
    if len(unique) != 1:
        return None
    row, option = next(iter(unique.values()))
    return {'type': 'set_control', 'tool': tool, 'label': row['label'],
            'field_id': row.get('id', ''), 'value': option['value']}


_AGENT_SECTIONS = {
    'Comment replies': ('Opens the social comment accounts and reply inbox.', 'Open replies'),
    'Editing clients': ('Finds editing gigs and prepares quotes and proposals.', 'Open'),
    'Sponsorships': ('Finds sponsors and prepares pitches and tracks replies.', 'Open'),
    'SaaS sales': ('Finds people with problems Storylens can solve; localhost promotion waits for hosting.', 'Open'),
    'Community': ('Finds relevant discussions and drafts useful replies; shown under Developer tools.', 'Open'),
    'Jobs': ('Finds roles and prepares truthful applications; shown under Developer tools.', 'Open'),
    'Development clients': ('Finds development projects and prepares quotes; shown under Developer tools.', 'Open'),
    'All workflows': ('Opens the existing suite workflows for delivery, commitments and research; under Developer tools.', 'Open workflows'),
}


@lru_cache(maxsize=1)
def _control_index():
    rows=[]
    for tool in FEATURES:
        for name,title,handler in controls(tool):
            rows.append({'tool':tool,'kind':'button','label':name,
                         'purpose':_description(name,title,handler,tool)})
        for field in form_fields(tool):
            row={**field,'tool':tool,'kind':'select' if field['type']=='select' else 'field'}
            row['purpose']=('Selects '+field['label']+' in '+FEATURES[tool][0]+'.' if field['type']=='select'
                            else 'Input control for '+field['label']+' in '+FEATURES[tool][0]+'.')
            rows.append(row)
    if 'aiAgents' in FEATURES:
        rows.extend({'tool':'aiAgents','kind':'section','label':name,'purpose':purpose,
                     'entry_button':button,'dynamic':True} for name,(purpose,button) in _AGENT_SECTIONS.items())
    for row in rows:
        row['_label_key'] = _option_key(row['label'])
        row['_option_keys'] = [(option, tuple({_option_key(option.get('label','')), _option_key(option.get('value',''))})) for option in row.get('options',())]
    return tuple(rows)


def search_controls(question, active='', snapshot=(), fields=(), limit=8):
    """Bounded source/live evidence for named nested controls across features.

    This performs knowledge retrieval only; hits are not permission or proof of
    a ready editor connection. A dynamic empty menu still exists in the product.
    """
    from .support_call_knowledge import _match
    query=_option_key(question)
    named=_match(' '+_normalize(question)+' ')
    rows=list(_control_index())
    if active in FEATURES:
        if fields:
            live_ids={field.get('id') for field in fields}
            live_labels={_normalize(field.get('label','')) for field in fields}
            rows=[row for row in rows if not (row['tool']==active and row['kind']=='select' and
                  (row.get('id') in live_ids or _normalize(row['label']) in live_labels))]
            rows.extend({**field,'tool':active,'kind':'select','live':True,
                         'purpose':'Current dropdown in '+FEATURES[active][0]+'.'} for field in fields)
        live_button_names={_normalize(row[0]) for row in snapshot}
        rows=[row for row in rows if not(row['tool']==active and row['kind']=='button' and _normalize(row['label']) in live_button_names)]
        for name,enabled,family in snapshot:
            rows.append({'tool':active,'kind':'button','label':name,'live':True,'disabled':not enabled,
                         'purpose':_description(name,'',family,active)})
    if named:
        rows=[row for row in rows if row['tool'] in named]
    generic_labels={'options','settings','format','type','language','mode','style','quality','speed'}
    generic_options={'auto','automatic','high','medium','low','on','off','yes','no','true','false',
                     'motion','short','long','full','source','default','english','hindi','en','hi',
                     'local','web','video','image','none','all','selected','current'}
    found=[]
    for row in rows:
        label=row['_label_key'] if '_label_key' in row else _option_key(row['label'])
        scoped=row['tool'] in named or not named and row['tool']==active
        exact_label=len(label)>=4 and _phrase_in(label,query) and (label not in generic_labels or scoped)
        option_keys = row['_option_keys'] if '_option_keys' in row else [(option,(_option_key(option.get('label','')),_option_key(option.get('value','')))) for option in row.get('options',())]
        matched_options=[option for option,keys in option_keys if any(len(key)>=4 and _phrase_in(key,query) and (key not in generic_options or exact_label) for key in keys)]
        # A feature inquiry can expose its controls even if no individual label
        # was named. Keep unrelated features out of this fallback.
        scoped=row['tool'] in named or not named and row['tool']==active
        list_request=bool(re.search(r'buttons?|controls?|settings?|options?|dropdown|menus?|बटन|सेटिंग|विकल्प|ऑप्शन',query))
        if not exact_label and not matched_options and not(scoped and list_request): continue
        score=(100+len(label) if exact_label else 0)+(120 if matched_options else 0)+(30 if row['tool'] in named else 10 if row['tool']==active else 0)
        item={key:value for key,value in row.items() if not key.startswith('_')}
        if matched_options:item['matched_options']=matched_options[:12]
        if row.get('dynamic') and row['kind']=='select':item['purpose']+=' Choices are loaded at runtime; an empty source list does not mean the control is absent.'
        found.append((score,item))
    found.sort(key=lambda value:(-value[0],value[1]['tool'],value[1]['label']))
    return tuple(row for _,row in found[:max(0,min(int(limit),20))])
