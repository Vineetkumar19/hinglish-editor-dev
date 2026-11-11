"""Deterministic commands keep local workflows usable without model/network load."""
import re


def parse(message):
    text = message.strip().strip('.!?')
    pairs = [
        (r'(?:index|import) document\s+(.+)', 'index_document', 'path'),
        (r'(?:search documents|find document evidence|answer with sources)\s+(.+)', 'answer_with_sources', 'query'),
        (r'(?:find|list|show) workspaces?(?:\s+(.+))?', 'find_workspace', 'query'),
        (r'(?:restore|resume) workspace\s+(.+)', 'restore_workspace', 'query'),
    ]
    for pattern, name, key in pairs:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            return name, {key:(match[1] or '').strip().strip('"')}
    if re.fullmatch(r'(?:show |list )?(?:local )?model profiles', text, re.I):
        return 'model_profiles', {}
    if re.fullmatch(r'(?:show |list )?document tasks', text, re.I):
        return 'list_document_tasks', {}
    match = re.fullmatch(r'(?:open|show)\s+(?:my\s+|google\s+)?calendar(?:\s+in\s+(day|week|month|agenda|schedule)\s+view)?', text, re.I)
    if match:
        return 'open_calendar', {'view':(match[1] or 'day').lower()}
    match = re.fullmatch(r'(?:check|show)\s+(?:my\s+)?calendar availability(?:\s+for)?\s+(\d{4}-\d{2}-\d{2})', text, re.I)
    if match:
        return 'calendar_availability', {'date':match[1]}
    match = re.fullmatch(
        r'prepare calendar event\s+(?P<title>.+)\s+(?:on\s+(?P<date>\d{4}-\d{2}-\d{2})|tomorrow)\s+at\s+'
        r'(?P<hour>\d{1,2})(?:[:.](?P<minute>[0-5]\d))?\s*(?P<meridiem>[ap]\.?m\.?)?\s+'
        r'for\s+(?P<duration>\d+)\s+minutes', text, re.I,
    )
    if match:
        hour = int(match['hour'])
        minute, meridiem = match['minute'], match['meridiem']
        if meridiem:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if meridiem.lower().startswith('p') else 0)
        elif hour > 23 or minute is None:
            return None
        clock = f'{hour:02d}:{minute or "00"}'
        when = f'{match["date"]}T{clock}' if match['date'] else f'tomorrow at {clock}'
        return 'create_calendar_event', {'title':match['title'], 'when':when, 'duration_minutes':int(match['duration'])}
    if re.fullmatch(
        r'(?:(?:can|could|would) you\s+)?(?:fix|schedule|set up|book|arrange)\s+(?:a\s+)?meeting'
        r'(?:\s+(?:in|on)\s+(?:the\s+)?(?:gmail|(?:google\s+)?calendar))?\s+(?:for\s+)?tomorrow', text, re.I,
    ):
        return 'ask_calendar_details', {}
    if re.fullmatch(r'(?:diagnose (?:my )?(?:pc|laptop)|why is my laptop hanging|laptop slow hai)', text, re.I):
        return 'sample_system', {'seconds':30}
    match = re.fullmatch(r'(?:switch (?:model )?to|use)\s+(9b|14b)(?:\s+q4)?', text, re.I)
    if match:
        return 'switch_model_profile', {'profile': 'local_' + match[1].lower() + '_q4'}
    return None


def summarize(name, result):
    if result.get('error'):
        return result['error']
    if name == 'answer_with_sources':
        return result['answer'] + '\n\n' + result['uncertainty']
    if name == 'index_document':
        return f"Indexed {result['pages']} pages/sections from {result['path']}. Status: {result['status']}. Document ID: {result['id']}."
    if name == 'find_workspace':
        return '\n'.join(f"{w['name']} — {w['captured_at']} — {w['id']}" for w in result['workspaces']) or 'No matching saved workspace.'
    if name == 'sample_system':
        return '\n\n'.join(f"{f['finding']}: {f['evidence']} {f['hypothesis']}" for f in result['findings']) + f"\nReport: {result['id']}. No process was stopped."
    if name == 'model_profiles':
        return '\n'.join(f"{key}: {value['tag']} — {'installed' if value['installed'] else 'not installed'}" for key,value in result['profiles'].items()) + '\nCloud is disabled.'
    if name == 'list_document_tasks':
        return 'See the document tasks in Workbench.'
    if name == 'open_calendar':
        return result['note']
    if name == 'calendar_availability':
        if result['status'] != 'schedule_observed':
            return result.get('note','I could not verify the schedule.')
        entries = '\n'.join(result['events']) or 'No events were visible for that date.'
        return f"{result['date']}\n{entries}\n{result['note']}"
    return 'Completed. Review the recorded result.'
