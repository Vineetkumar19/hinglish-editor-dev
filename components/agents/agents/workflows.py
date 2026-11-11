"""Evidence-led preparation for Suite roles. Incoming text is data, never authority.

These planners do not send, publish, edit media projects or execute repositories.
The owner/GPT can supply structured source-bound facts; uncertain extraction is
kept reviewable instead of making a local model call behind the operator's back.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from core import config
from core.workflow_contracts import digest, require_fields
from core.workflow_store import Conflict


def contact(store, contact_id):
    row = store.one('SELECT * FROM leads WHERE id=?', (contact_id,))
    if not row:
        raise ValueError('Select an existing contact/opportunity ID')
    return row


def client_delivery(task, ledger):
    inputs = task['input']
    require_fields(inputs, ('contact_id', 'brief', 'scope', 'price', 'deliverables'))
    lead = contact(ledger.store, inputs['contact_id'])
    if lead['agent'] not in ('video_client', 'fullstack_sales'):
        raise ValueError('Delivery starts from an editing or development opportunity; sponsorship retains its deals')
    if lead['status'] not in ('qualified', 'interested', 'closed_won'):
        raise ValueError('The enquiry is not qualified for delivery')
    require_fields(inputs['brief'], ('source_ref', 'text'))
    require_fields(inputs['price'], ('amount', 'currency', 'evidence'))
    owner_internal = inputs.get('commission_type') == 'owner_internal'
    if not isinstance(inputs['price']['amount'], (float, int)) or inputs['price']['amount'] < 0 or (inputs['price']['amount'] == 0 and not owner_internal):
        raise ValueError('Price must be a positive agreed amount')
    ids = [d['id'] for d in inputs['deliverables']]
    if len(ids) != len(set(ids)):
        raise ValueError('Deliverable IDs must be unique')
    for d in inputs['deliverables']:
        require_fields(d, ('id', 'description', 'acceptance'))
    for feedback in inputs.get('feedback', []):
        require_fields(feedback, ('deliverable_id', 'source_ref', 'text', 'timestamp'))
        if feedback['deliverable_id'] not in ids:
            raise ValueError('Feedback must map to a known deliverable')
        dt.datetime.fromisoformat(feedback['timestamp'].replace('Z', '+00:00'))
    scope = {key: inputs[key] for key in ('contact_id', 'brief', 'scope', 'price', 'deliverables')}
    scope['commission_type'] = inputs.get('commission_type', 'client')
    approved = ledger.store.kv_get('workflow_scope', task['task_id'], {})
    scope_hash = digest(scope)
    changed = bool(approved and approved.get('scope_hash') != scope_hash)
    base = {**scope, 'brief_revision': task['revision'], 'scope_hash': scope_hash,
        'scope_expansion': changed, 'feedback': inputs.get('feedback', []),
        'affected_outputs': sorted({f['deliverable_id'] for f in inputs.get('feedback', [])}),
        'milestones': inputs.get('milestones') or [
            {'name': 'Confirm scope and assets', 'state': 'proposed'},
            {'name': 'Review first delivery', 'state': 'proposed'},
            {'name': 'Resolve recorded revisions', 'state': 'proposed'}],
        'work_request': {'project': 'storylens' if lead['agent'] == 'video_client' else 'repository',
            'contact_id': lead['id'], 'opportunity_id': lead['id'],
            'brief_revision': task['revision'], 'scope_hash': scope_hash,
            'brief': inputs['brief'], 'scope': inputs['scope'], 'deliverables': inputs['deliverables'],
            'feedback': inputs.get('feedback', []),
            'affected_outputs': sorted({f['deliverable_id'] for f in inputs.get('feedback', [])}),
            'artifact_refs': inputs.get('assets', []), 'deployment_authorized': False},
        'missing_assets': inputs.get('missing_assets', [])}
    base['commission_type'] = inputs.get('commission_type', 'client')
    base['work_request']['work_order'] = inputs.get('work_order', {})
    if inputs.get('phase', 'scope') == 'scope':
        ledger.verify_artifacts(inputs.get('assets', []))
        return base, 'prepare', lead['id'], inputs.get('assets', [])
    if not approved or changed:
        raise Conflict('Review this exact scope/price before preparing the delivery package')
    require_fields(inputs, ('recipient', 'files'))
    if inputs['recipient'] != lead['email']:
        raise ValueError('Delivery recipient must match the selected contact')
    refs = ledger.verify_artifacts(inputs['files'])
    if set(inputs.get('file_deliverables', {})) != set(ids):
        raise ValueError('Map every deliverable to its exact artifact ID')
    if not set(inputs['file_deliverables'].values()) <= {r['artifact_id'] for r in refs}:
        raise ValueError('Deliverable mapping names an absent file')
    base.update(files=refs, recipient=inputs['recipient'],
        checklist={'scope_reviewed': True, 'files_present_and_hashed': True,
                   'recipient_resolved': True, 'acceptance_evidence': inputs.get('acceptance_evidence', [])},
        subject=inputs.get('subject', 'Delivery for review'), body=inputs.get('body') or
            'Please review the attached deliverables: ' + '; '.join(d['description'] for d in inputs['deliverables']) + '.',
        package_state='prepared; not sent')
    if not base['checklist']['acceptance_evidence']:
        raise ValueError('Delivery requires source-linked acceptance evidence')
    return base, 'delivery.package' if inputs.get('delivery_mode') == 'local_package' else 'delivery.send', inputs['recipient'], refs


def inbox_commitment(task, ledger):
    inputs = task['input']
    require_fields(inputs, ('messages',))
    suggestions, questions = [], []
    for message in inputs['messages']:
        require_fields(message, ('source_ref', 'source_id', 'text', 'contact_id', 'received_at'))
        contact(ledger.store, message['contact_id'])
        received = dt.datetime.fromisoformat(message['received_at'].replace('Z', '+00:00'))
        if not received.tzinfo:
            raise ValueError('Message receipt time needs a timezone')
        msg_key = digest({'source_id': message['source_id'], 'source_ref': message['source_ref']})
        previous = ledger.store.kv_get('commitment_sources', msg_key)
        if previous and previous['text_hash'] != digest(message['text']):
            raise Conflict('Reimport changed source text; provide a distinct source revision')
        commitments = message.get('commitments')
        if commitments is None:
            commitments = [{'quote': s.strip(), 'description': s.strip(), 'status': 'proposed'}
                for s in re.split(r'(?<=[.!?])\s+|\n', message['text'])
                if re.search(r'\b(?:will|by|deadline|deliver|send|agreed|confirm|could you|please)\b', s, re.I)]
        for c in commitments:
            require_fields(c, ('quote', 'description'))
            if c['quote'] not in message['text']:
                raise ValueError('Commitment quote is absent from its source')
            status = c.get('status', 'proposed')
            if status not in ('proposed', 'accepted', 'completed', 'disputed'):
                raise ValueError('Unknown commitment status')
            if status != 'proposed' and not c.get('status_evidence'):
                raise ValueError('Accepted/completed/disputed commitments require explicit evidence')
            if c.get('status_evidence') and c['status_evidence'] not in message['text']:
                raise ValueError('Status evidence is absent from the selected source')
            if status == 'accepted' and (not re.search(r'\b(?:agreed|accepted|confirmed|yes)\b', c['status_evidence'], re.I)
                    or re.search(r'\b(?:not|never|no)\b', c['status_evidence'], re.I)):
                raise ValueError('A suggestion or negated agreement cannot become an accepted commitment')
            matches = re.findall(r'\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?', c['quote'])
            deadline, uncertain = '', ''
            if len(matches) == 1:
                parsed = dt.datetime.fromisoformat(matches[0].replace('Z', '+00:00'))
                if 'T' not in matches[0]:
                    deadline = matches[0]
                    uncertain = 'Date is explicit; time of day is unspecified'
                elif parsed.tzinfo is None:
                    uncertain = 'Time has no explicit timezone; confirm before scheduling'
                else:
                    deadline = parsed.astimezone(ZoneInfo(config.get('TIMEZONE', 'Asia/Kolkata'))).isoformat()
            else:
                uncertain = 'No unique explicit ISO date; resolve the deadline with the owner'
            cid = digest({'source': msg_key, 'quote': c['quote']})
            existing = ledger.store.kv_get('commitments', cid)
            suggestions.append({'id': cid, 'description': c['description'], 'source_ref': message['source_ref'],
                'source_id': message['source_id'], 'contact_id': message['contact_id'], 'quote': c['quote'],
                'status': existing['status'] if existing else status, 'deadline': deadline,
                'deadline_evidence': c['quote'] if deadline else '', 'uncertainty': uncertain,
                'already_imported': bool(existing), 'source_key': msg_key, 'text_hash': digest(message['text'])})
            if uncertain:
                questions.append({'commitment_id': cid, 'question': uncertain})
    return {'commitments': suggestions, 'questions': questions,
        'reply_drafts': inputs.get('reply_drafts', []), 'outgoing_authorized': False}, 'prepare', '', []


def learning_evidence(task, ledger):
    inputs = task['input']
    require_fields(inputs, ('goal', 'period', 'entries'))
    facts = []
    refs = []
    for entry in inputs['entries']:
        require_fields(entry, ('description', 'stage', 'source_ref', 'context'))
        if entry['stage'] not in ('reading', 'attempted', 'demonstrated'):
            raise ValueError('Learning stage must distinguish reading, attempted and demonstrated')
        if entry['context'] != 'personal_lab':
            raise PermissionError('This personal workflow accepts personal labs only; employer material needs a separately authorized adapter')
        evidence = ledger.verify_artifacts(entry.get('artifacts', []))
        if entry['stage'] == 'demonstrated' and not evidence:
            raise ValueError('Demonstrated completion needs an artifact with evidence')
        facts.append({**entry, 'artifacts': evidence})
        refs.extend(evidence)
    summary = '\n'.join(f"{e['stage'].title()} (personal lab): {e['description']} [{e['source_ref']}]" for e in facts)
    return {'goal': inputs['goal'], 'period': inputs['period'], 'entries': facts,
        'exercise': inputs.get('exercise', 'Complete a small personal lab for this goal and retain its commands, outputs and checks.'),
        'progress_summary': summary, 'interview_draft': summary, 'client_experience_claim': False}, 'prepare', '', refs


def content_release(task, ledger):
    inputs = task['input']
    require_fields(inputs, ('body_revision', 'packages', 'edit_approval_ref', 'rights_evidence'))
    packages = []
    refs = []
    intros = set()
    identity_by_hash = {}
    for p in inputs['packages']:
        require_fields(p, ('platform', 'account', 'time', 'title', 'caption', 'artifact', 'intro_id'))
        when = dt.datetime.fromisoformat(p['time'].replace('Z', '+00:00'))
        if not when.tzinfo:
            raise ValueError('Release time must include an explicit timezone')
        tags = set(re.findall(r'#([A-Za-z0-9_]+)', p['caption']))
        if len(tags) < 10:
            raise ValueError('Release metadata needs at least ten distinct relevant English hashtags')
        if re.search(r'[\u0900-\u0dff]', p['title'] + p['caption']):
            raise ValueError('Audience title and caption must use the owner’s English-copy preference')
        artifact = ledger.verify_artifacts([p['artifact']])[0]
        if artifact['project'].lower() != 'storylens' or (artifact['approval_status'] != 'approved' and not inputs.get('preview_only')):
            raise ValueError('Release consumes approved StoryLens exports only')
        from core.workflow_media import inspect_video
        media = inspect_video(artifact['locator'])
        prior_intro = identity_by_hash.setdefault(artifact['content_hash'], p['intro_id'])
        if prior_intro != p['intro_id']:
            raise ValueError('Distinct intro IDs cannot silently reuse the identical rendered file')
        intros.add(p['intro_id'])
        packages.append({**p, 'artifact': artifact, 'media': media, 'body_revision': inputs['body_revision'],
                         'trial': bool(inputs.get('cinematic_trials')), 'scheduler_owner': 'storylens',
                         'preview_only': bool(inputs.get('preview_only'))})
        refs.append(artifact)
    if inputs.get('cinematic_trials') and len(intros) != 3:
        raise ValueError('Cinematic trials require three distinct intro IDs for the shared body revision')
    keys = [(p['platform'], p['account'], p['intro_id']) for p in packages]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate release destination/intro')
    return {'packages': packages, 'body_revision': inputs['body_revision'],
        'edit_approval_ref': inputs['edit_approval_ref'], 'rights_evidence': inputs['rights_evidence'],
        'scheduler_owner': 'storylens', 'state': 'Draft previews; edit approval is still required' if inputs.get('preview_only') else 'upload-ready packages; publication not performed'}, 'prepare', '', refs


def saas_demand(task, ledger):
    from core.mailer import SuppressionList
    from agents.saas_sales.product import check_claims
    inputs = task['input']
    require_fields(inputs, ('capabilities',))
    live_research = bool(inputs.get('research_query'))
    if live_research:
        from agents.saas_sales.research import research_signals
        signals = research_signals(inputs['research_query'], inputs['capabilities'], ledger.store)
    else:
        require_fields(inputs, ('signals',))
        signals = inputs['signals']
    if len(signals) > 20:
        raise ValueError('Initial demand research is limited to 20 selected enquiries')
    ranked, contacts = [], set()
    for signal in signals:
        require_fields(signal, ('contact_id', 'source_ref', 'observed_at', 'expressed_need', 'source_text'))
        lead = contact(ledger.store, signal['contact_id'])
        if signal['expressed_need'] not in signal['source_text']:
            raise ValueError('Expressed need must be quoted from the source')
        identity = (lead['email'] or lead['source_url'] or lead['id']).strip().lower()
        if identity in contacts or lead['status'] == 'suppressed' or SuppressionList(ledger.store).contains(lead['email']):
            continue
        contacts.add(identity)
        prior = ledger.store.one('SELECT id FROM send_log WHERE lower(addr_to)=? LIMIT 1', (identity,)) if lead['email'] else None
        matches, flags = [], []
        for feature in signal.get('capability_ids', []):
            capability = inputs['capabilities'].get(feature, {})
            if capability.get('status') == 'working' and capability.get('evidence_ref'):
                matches.append(feature)
            else:
                flags.append(f'{feature}: upcoming or unverified; do not promise it')
        prior = bool(prior or lead['status'] in ('posted', 'interested', 'disqualified'))
        draft = signal.get('draft', '')
        research_draft = live_research and signal.get('research_only_draft')
        claim_flags = check_claims(draft)
        flags.extend(claim_flags)
        ranked.append({'contact_id': lead['id'], 'source_ref': signal['source_ref'],
            'observed_at': signal['observed_at'], 'expressed_need': signal['expressed_need'],
            'qualification_facts': matches, 'inferred_signals': signal.get('inferred_signals', []),
            'score': len(matches), 'flags': flags, 'draft': draft,
            'prior_contact_attempt': bool(prior), 'target': lead['email'] or lead['source_url'],
            'draft_reviewable': bool(draft and not prior and
                                      (not claim_flags if research_draft else matches and not flags)),
            'research_only_draft': bool(research_draft),
            'status': 'research_only', 'owner_role': 'saas_sales'})
    ranked.sort(key=lambda r: (-r['score'], r['contact_id']))
    return {'ranked_needs': ranked, 'drafts': [r for r in ranked if r['draft_reviewable']][:5],
            'discovery_enabled': live_research, 'sending_enabled': False,
            'next_action': 'Review the cited discussion and its draft before opening a manual handoff'}, 'prepare', '', []
