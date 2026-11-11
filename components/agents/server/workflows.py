"""Additive capability cards and task reviews in the existing authenticated shell."""
from __future__ import annotations

import json
import re
import time
from urllib.parse import quote, unquote

from core import config
from core.workflow_contracts import ROLES
from core.workflow_service import WorkflowService
from core.workflow_store import Conflict
from server import console


def render_payload(payload):
    """Show reviewable content first; keep contract internals in disclosure."""
    esc = console.esc
    parts = []
    if payload.get('planning_review'):
        brain = payload['planning_review']
        plan = brain['plan']
        parts.append(f"<article class=card><h3>Planning review · {esc(brain['model'])}</h3><p>{esc(plan['summary'])}</p>"
            + '<ol>' + ''.join(f"<li>{esc(s['description'])}</li>" for s in plan['steps']) + '</ol>'
            + (f"<p style='white-space:pre-wrap'>{esc(plan['draft_reply'])}</p>" if plan['draft_reply'] else '')
            + ''.join(f"<p>{esc(q)}</p>" for q in plan['questions']) + '<p class=hint>Model suggestions await your review. No action was authorized by the model.</p></article>')
    if payload.get('brief'):
        brief = payload['brief']
        parts.append(f"<article class=card><h3>Brief</h3><p>{esc(brief['text'])}</p><p class=hint>Source: {esc(brief['source_ref'])}</p></article>")
    if payload.get('scope'):
        price = payload.get('price', {})
        parts.append(f"<article class=card><h3>Scope and price</h3><p>{esc(payload['scope'])}</p>"
            f"<p><b>{esc(price.get('currency', ''))} {esc(price.get('amount', ''))}</b></p>"
            f"<p class=hint>Agreement: {esc(price.get('evidence', ''))}</p>"
            + ('<p class=note>Scope changed since the previous approval.</p>' if payload.get('scope_expansion') else '') + '</article>')
    for name, label in (('deliverables', 'Deliverables'), ('milestones', 'Milestones'), ('feedback', 'Feedback')):
        if payload.get(name):
            items = ''.join(f"<li>{esc(p.get('description') or p.get('name') or p.get('text', ''))}"
                + (f" — {esc(p['acceptance'])}" if p.get('acceptance') else '')
                + (f" ({esc(p['deliverable_id'])}, {esc(p.get('timestamp', ''))})" if p.get('deliverable_id') else '') + '</li>' for p in payload[name])
            parts.append(f'<article class=card><h3>{label}</h3><ul>{items}</ul></article>')
    if payload.get('recipient') or payload.get('account'):
        parts.append(f"<article class=card><h3>Destination</h3><p>{esc(payload.get('recipient') or payload.get('account'))}</p>"
            f"<p>{esc(payload.get('platform', ''))} {esc(payload.get('time', ''))}</p>"
            f"<h3>{esc(payload.get('subject') or payload.get('title', ''))}</h3>"
            f"<p style='white-space:pre-wrap'>{esc(payload.get('body') or payload.get('caption', ''))}</p></article>")
    files = payload.get('files', []) + ([payload['artifact']] if payload.get('artifact') else [])
    if files:
        from pathlib import Path
        parts.append('<article class=card><h3>Exact delivery files</h3><ul>' + ''.join(
            f"<li>{esc(Path(r['locator']).name)} — revision {esc(r['revision'])}<br>"
            f"<small>{esc(r['content_hash'])}</small></li>" for r in files) + '</ul></article>')
    for c in payload.get('commitments', []):
        parts.append(f"<article class=card><h3>{esc(c['description'])}</h3><p>{esc(c['status'])} · {esc(c['deadline'] or 'Deadline needs clarification')}</p>"
            f"<blockquote>{esc(c['quote'])}</blockquote><p class=hint>{esc(c['source_ref'])}</p><p>{esc(c['uncertainty'])}</p></article>")
    if payload.get('progress_summary'):
        parts.append(f"<article class=card><h3>{esc(payload['goal'])}</h3><p>{esc(payload['period'])}</p><p style='white-space:pre-wrap'>{esc(payload['progress_summary'])}</p></article>")
    if payload.get('manifest'):
        m = payload['manifest']
        parts.append(f"<article class=card><h3>{esc(m['question'])}</h3><p>{esc(m['verdict'])}</p><p>{esc(m['scope'])}</p>"
            f"<p>Baseline MRR: {esc(payload['baseline']['mrr'])} · Candidate MRR: {esc(payload['candidate']['mrr'])}</p></article>")
    for package in payload.get('packages', []):
        parts.append(f"<h3>Intro {esc(package['intro_id'])} · body {esc(package['body_revision'])}</h3>" + render_payload(package))
    for need in payload.get('ranked_needs', []):
        parts.append(f"<article class=card><h3>{esc(need['expressed_need'])}</h3><p>{esc(need['source_ref'])}</p>"
            f"<p>Supported matches: {esc(', '.join(need['qualification_facts']) or 'None')}</p>"
            f"<p>{esc('; '.join(need['flags']))}</p><p style='white-space:pre-wrap'>{esc(need['draft'])}</p></article>")
    if payload.get('package_state'):
        parts.append(f"<p class=note>{esc(payload['package_state'])}</p>")
    parts.append('<details><summary>Source records and exact review data</summary><pre>'
                 + esc(json.dumps(payload, indent=2, ensure_ascii=False)) + '</pre></details>')
    return ''.join(parts)


class WorkflowViews:
    def __init__(self, handler, query):
        self.h = handler
        self.query = query
        self.qs = handler._token_qs(query)
        self.service = WorkflowService(handler.store)

    def respond(self, title, content):
        # Immutable hashes and canonical filenames can be wider than a phone.
        content = '<div style="min-width:0;overflow-wrap:anywhere">' + content + '</div>'
        self.h._send(200, console.shell(title, self.h._rail('workflows', self.query), content))

    def get(self, path):
        if path.startswith('/workflows/artifact/'):
            self.artifact(path)
        elif path == '/api/workflows':
            self.h._json(200, {'roles': ROLES, 'tasks': self.service.ledger.list()})
        elif path == '/workflows':
            self.home()
        elif re.fullmatch(r'/api/workflows/task_[a-f0-9]+/backup', path):
            self.h._json(200, self.service.ledger.backup_task(path.split('/')[-2]))
        elif re.fullmatch(r'/workflows/task_[a-f0-9]+', path):
            self.detail(path.rsplit('/', 1)[1])
        elif re.fullmatch(r'/api/workflows/task_[a-f0-9]+', path):
            task = self.service.ledger.get(path.rsplit('/', 1)[1])
            self.h._json(200 if task else 404, task or {'error': 'Task not found'})
        else:
            return False
        return True

    def artifact(self, path):
        parts = path.split('/')
        if len(parts) != 5:
            return self.h._json(404, {'error': 'Artifact not found'})
        row = self.h.store.one('SELECT ref_json FROM suite_artifacts WHERE artifact_id=? AND revision=?',
            (unquote(parts[3]), unquote(parts[4])))
        if not row:
            return self.h._json(404, {'error': 'Artifact not found'})
        try:
            ref = self.service.ledger.verify_artifacts([json.loads(row['ref_json'])])[0]
            from pathlib import Path
            file = Path(ref['locator'])
            size = file.stat().st_size
            start, end, status = 0, size-1, 200
            requested = self.h.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
                if not match:
                    return self.h._json(416, {'error':'Unsupported range'})
                start = int(match[1]); end = min(int(match[2]),end) if match[2] else end
                if start > end:
                    return self.h._json(416, {'error':'Range outside file'})
                status = 206
            self.h.send_response(status)
            self.h.send_header('Content-Type', 'video/mp4' if ref['type'] == 'mp4' else 'application/octet-stream')
            self.h.send_header('X-Content-Type-Options','nosniff')
            self.h.send_header('Cache-Control','private, no-store')
            self.h.send_header('Accept-Ranges','bytes')
            self.h.send_header('Content-Length',str(end-start+1))
            if status == 206:
                self.h.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.h.end_headers()
            with file.open('rb') as stream:
                stream.seek(start)
                remaining = end-start+1
                while remaining:
                    chunk = stream.read(min(65536,remaining))
                    if not chunk:
                        break
                    self.h.wfile.write(chunk); remaining -= len(chunk)
        except (ValueError,OSError) as exc:
            return self.h._json(409, {'error':str(exc)[:300]})

    def post(self, path):
        if not path.startswith(('/workflows', '/api/workflows')):
            return False
        if console.demo_mode():
            self.h._json(403, {'error': 'Demo mode is read-only'})
            return True
        # The existing gateway token is required for every new write, including
        # loopback. No new unauthenticated service is exposed.
        if not config.get('DASHBOARD_TOKEN'):
            self.h._json(403, {'error': 'Configure the existing dashboard token before workflow writes'})
            return True
        form = self.h._form()
        try:
            if self.h.server.integrated and path == '/workflows/saas-settings':
                from agents.saas_sales.research import save_settings
                save_settings(self.h.store, form.get('public_url', ''), form['hosting'],
                              json.loads(form.get('capabilities', '{}')))
                self.h._redirect('/workflows' + self.qs + '#saas-demand')
                return True
            if self.h.server.integrated and path == '/workflows/saas-research':
                from agents.saas_sales.research import launch_settings
                query = str(form.get('query') or '').strip()
                if not 10 <= len(query) <= 500:
                    raise ValueError('Describe a specific editing workflow or audience in 10–500 characters.')
                task = self.service.create('saas_sales', query, {
                    'research_query': query,
                    'capabilities': launch_settings(self.h.store)['capabilities'],
                }, f'ui:saas_research:{time.time_ns()}')
                import threading
                threading.Thread(target=self.service.prepare, args=(task['task_id'],), daemon=True).start()
            elif self.h.server.integrated and re.fullmatch(r'/workflows/task_[a-f0-9]+/saas-outcome', path):
                task_id = path.split('/')[-2]
                self.service.record_outcome(task_id, form['contact_id'], form['status'],
                                            form['source_ref'], form['quote'])
                task = self.service.ledger.get(task_id)
            elif path in ('/workflows/create', '/api/workflows'):
                if form.get('role') == 'client_delivery' and 'brief_text' in form:
                    inputs = {'contact_id': form['contact_id'], 'brief': {'source_ref': form['source_ref'], 'text': form['brief_text']},
                        'scope': form['scope'], 'price': {'amount': float(form['amount']), 'currency': form['currency'], 'evidence': form['price_evidence']},
                        'deliverables': [{'id': 'delivery-1', 'description': form['deliverable'], 'acceptance': form['acceptance']}], 'phase': 'scope'}
                else:
                    inputs = form.get('inputs', form.get('inputs_json', {}))
                    if isinstance(inputs, str):
                        inputs = json.loads(inputs or '{}')
                if not isinstance(inputs, dict):
                    raise ValueError('Workflow inputs must be an object')
                if self.h.server.integrated:
                    engine = form.get('brain') or inputs.get('_brain')
                    if engine not in (None, '', 'manual', 'chatgpt'):
                        raise ValueError('Storylens planning uses ChatGPT.')
                if form.get('brain'):
                    from core.workflow_brain import ENGINES
                    if form['brain'] not in ENGINES:
                        raise ValueError('Unknown planning model')
                    inputs['_brain'] = form['brain']
                task = self.service.create(form['role'], form['intent'], inputs,
                    form.get('idempotency_key') or f"ui:{form['role']}:{time.time_ns()}",
                    device_id=form.get('device_id'), permissions=form.get('permissions'), budgets=form.get('budgets'))
                if inputs.get('_brain', 'manual') != 'manual' and not path.startswith('/api/'):
                    import threading
                    threading.Thread(target=self.service.prepare, args=(task['task_id'],), daemon=True).start()
                else:
                    task = self.service.prepare(task['task_id'])
            elif path == '/api/workflows/artifacts':
                result = self.service.ledger.register_artifact(form['path'], project=form['project'],
                    revision=form['revision'], evidence=form['evidence'], artifact_id=form.get('artifact_id'),
                    approval_status=form.get('approval_status', 'unreviewed'))
                self.h._json(201, result)
                return True
            elif re.fullmatch(r'/api/workflows/task_[a-f0-9]+/outcome', path):
                self.h._json(200, self.service.record_outcome(path.split('/')[-2], **form))
                return True
            else:
                match = re.fullmatch(r'/(?:api/)?workflows/(task_[a-f0-9]+)/(prepare|approve|reject|pause|resume|cancel|revise|dispatch|request-work|request-diagnostics|delete-content)', path)
                if not match:
                    self.h._json(404, {'error': 'Unknown workflow action'})
                    return True
                task_id, action = match.groups()
                if action == 'delete-content':
                    if form.get('confirmation') != task_id:
                        raise ValueError('Confirm the exact task ID to delete its saved content')
                    task = self.service.ledger.redact_task(task_id)
                elif action in ('pause', 'resume', 'cancel'):
                    task = self.service.control(task_id, action)
                elif action == 'revise':
                    inputs = form.get('inputs', form.get('inputs_json'))
                    if isinstance(inputs, str):
                        inputs = json.loads(inputs)
                    task = self.service.ledger.revise(task_id, inputs, int(form['revision']))
                elif action in ('approve', 'reject'):
                    task = self.service.decide(task_id, action == 'approve', form.get('approval_id'))
                elif action == 'dispatch':
                    task = self.service.dispatch(task_id)
                elif action == 'request-work':
                    task = self.service.request_work(task_id)
                elif action == 'request-diagnostics':
                    task = self.service.request_diagnostics(task_id)
                else:
                    task = self.service.prepare(task_id)
            if path.startswith('/api/'):
                self.h._json(200, task)
            else:
                self.h._redirect('/workflows/' + task['task_id'] + self.qs)
        except (ValueError, KeyError, PermissionError, RuntimeError, OSError) as exc:
            self.h._json(409 if isinstance(exc, Conflict) else 400, {'error': str(exc)[:500]})
        return True

    def home(self):
        esc = console.esc
        cards = ''.join(f"<article class=card><h3>{esc(ROLES.get(t['role'], t['role']))}</h3>"
            f"<a href='/workflows/{t['task_id']}{self.qs}'>{esc(t['envelope']['intent'])}</a> "
            f"<span class=tag>{esc('paused' if t['paused'] else t['state'])}</span>"
            f"<p>{esc(t['result'].get('verified_result') or t['result'].get('error') or t['result'].get('next_valid_action', 'Queued'))}</p></article>"
            for t in self.service.ledger.list())
        options = ''.join(f"<option value='{key}'>{esc(name)}</option>" for key, name in ROLES.items())
        leads = self.h.store.query("SELECT id,company,status FROM leads WHERE agent IN ('video_client','fullstack_sales') AND status IN ('qualified','interested','closed_won') ORDER BY updated_at DESC LIMIT 100")
        lead_options = ''.join(f"<option value='{esc(l['id'])}'>{esc(l['company'])} — {esc(l['status'])}</option>" for l in leads)
        from core.workflow_brain import ENGINES
        engines = {'chatgpt': ENGINES['chatgpt']} if self.h.server.integrated else ENGINES
        brain_select = '<label>Planning brain</label><select name=brain>' + ''.join(
            f"<option value='{key}'>{esc(label)}</option>" for key, (label, _) in engines.items()) + '</select><p class=hint>ChatGPT uses your existing Codex sign-in.</p>'
        forms = '' if console.demo_mode() else f"""
        <h2>Check readiness</h2><form class=card method=post action='/workflows/create{self.qs}'>
        <input type=hidden name=role value=system_health><input type=hidden name=intent value='Check workflow readiness'>
        <p>Check configured dependencies and show the next action for each blocker.</p><button class=go>Check now</button></form>
        <h2>Start a client delivery</h2><form class=card method=post action='/workflows/create{self.qs}'>
        <input type=hidden name=role value=client_delivery>
        <label>Qualified enquiry</label><select name=contact_id required>{lead_options}</select>
        <label>Project name</label><input type=text name=intent required>
        <label>Brief source</label><input type=text name=source_ref required>
        <label>Client brief</label><textarea name=brief_text required></textarea>
        <label>Scope</label><textarea name=scope required></textarea>
        <label>Agreed price</label><input type=number min=1 step=0.01 name=amount required>
        <label>Currency</label><input type=text name=currency value=INR required>
        <label>Price agreement evidence</label><input type=text name=price_evidence required>
        <label>Deliverable</label><input type=text name=deliverable required>
        <label>Acceptance criteria</label><textarea name=acceptance required></textarea>
        {brain_select}
        <button class=go {'disabled' if not leads else ''}>Prepare scope review</button>
        {'<p>No qualified editing or development enquiry is available yet.</p>' if not leads else ''}</form>
        <details><summary>Import a prepared workflow request</summary>
        <p>Use selected, source-linked material. Importing never sends a message or publishes content.</p>
        <form class=card method=post action='/workflows/create{self.qs}'>
        <label>Workflow</label><select name=role>{options}</select>
        <label>Task name</label><input type=text name=intent required>
        <label>Prepared request (JSON)</label><textarea name=inputs_json required>{{}}</textarea>
        {brain_select}
        <button class=go>Prepare for review</button></form></details>"""
        legacy = self.h.store.query('SELECT thread_id,agent,status,updated_at FROM threads ORDER BY updated_at DESC LIMIT 20')
        legacy_html = '<h2>Existing workflow runs</h2><p class=hint>Runner completion is separate from confirmed delivery or publication.</p>'
        legacy_html += '<table><tr><th>Workflow</th><th>Runner state</th><th>Delivery evidence</th></tr>'
        for run in legacy:
            messages = self.h.store.one("SELECT COUNT(*) AS n FROM messages WHERE thread_id=? AND direction='out' AND provider_id!='' AND provider_id NOT LIKE 'dryrun-%'", (run['thread_id'],))
            legacy_html += f"<tr><td>{esc(run['agent'])}</td><td>{esc(run['status'])}</td><td>{messages['n']} provider receipts recorded</td></tr>"
        legacy_html += '</table>'
        demand = self.saas_forms() if self.h.server.integrated and not console.demo_mode() else ''
        self.respond('Workflows — Agent Suite', '<h1>Workflows</h1><p class=lede>Readiness, delivery and evidence in your existing workspace.</p>' + demand + forms + '<h2>Tasks</h2>' + (cards or console.empty('No tasks yet', 'Check readiness or prepare a client brief.')) + legacy_html)

    def saas_forms(self):
        from agents.saas_sales.research import launch_settings

        settings = launch_settings(self.h.store)
        esc = console.esc
        stage = esc(settings['stage'])
        hosting = settings['hosting']
        return f"""
        <section id='saas-demand'>
        <h2>Storylens SaaS demand research</h2>
        <form class=card method=post action='/workflows/saas-research{self.qs}'>
        <p>Search public discussions for a specific editing problem, rank relevance, and prepare a disclosed question for review.</p>
        <label for=saas-query>Workflow problem or audience</label>
        <input type=text id=saas-query name=query minlength=10 maxlength=500 required
               placeholder='Premiere editors losing time removing pauses from interviews'>
        <button class=go>Search public discussions</button></form>
        <details class=card><summary>Launch settings</summary>
        <form method=post action='/workflows/saas-settings{self.qs}'>
        <p>Product stage: {stage}. External product promotion is parked. Research questions stay non-promotional.</p>
        <label for=saas-hosting>Hosting status</label>
        <select id=saas-hosting name=hosting>
        <option value=local {'selected' if hosting == 'local' else ''}>Localhost only</option>
        <option value=public {'selected' if hosting == 'public' else ''}>Public URL supplied, verification pending</option>
        </select>
        <label for=saas-url>Public HTTPS URL when available</label>
        <input type=text id=saas-url name=public_url value='{esc(settings['public_url'])}'>
        <label for=saas-capabilities>Capabilities and evidence (JSON)</label>
        <textarea id=saas-capabilities name=capabilities>{esc(json.dumps(settings['capabilities'], indent=2))}</textarea>
        <p>Set each capability to working, planned or unverified. Working capabilities require an evidence reference.</p>
        <button class=go>Save launch settings</button>
        </form></details></section>"""

    def detail(self, task_id):
        task = self.service.ledger.get(task_id)
        if not task:
            return self.h._json(404, {'error': 'Task not found'})
        esc = console.esc
        result = task['result']
        body = f"<p><a href='/workflows{self.qs}'>← Workflows</a></p><h1>{esc(task['envelope']['intent'])}</h1>"
        if task['state'] in ('queued','planning','running') and not task['paused']:
            body = '<meta http-equiv="refresh" content="5">' + body
        body += f"<p><span class=tag>{esc('paused' if task['paused'] else task['state'])}</span> Revision {task['revision']}</p>"
        body += f"<p>{esc(result.get('verified_result', ''))}</p><p>{esc(result.get('next_valid_action', ''))}</p>"
        if result.get('error'):
            body += f"<p class=note>{esc(result['error'])}</p>"
        if result.get('checks'):
            for c in result['checks']:
                body += f"<article class=card><h3>{esc(c['id'])}: {esc(c['classification'])}</h3><p>{esc(c.get('detail', ''))}</p><p>{esc(c.get('next_action', ''))}</p><details><summary>Observed evidence</summary><pre>{esc(json.dumps(c, indent=2))}</pre></details></article>"
        else:
            body += render_payload(result.get('prepared', result))
        receipt = result.get('receipt', {})
        if receipt:
            body += '<article class=card><h3>Receiving application result</h3><p>' + esc(receipt.get('verified_result') or receipt.get('status','')) + '</p>'
            if receipt.get('package_folder'):
                body += '<p>' + esc(receipt['package_folder']) + '</p><p>Saved locally. Nothing sent.</p>'
            body += '</article>'
        artifacts = result.get('prepared',{}).get('files',[]) + receipt.get('artifacts',[])
        for ref in artifacts:
            if ref['type'] == 'mp4':
                url = '/workflows/artifact/' + quote(ref['artifact_id'],safe='') + '/' + quote(ref['revision'],safe='') + self.qs
                body += f"<article class=card><h3>Review the exact video</h3><video aria-label='Delivery video preview' controls preload=metadata style='max-width:100%;max-height:520px' src='{esc(url)}'></video></article>"
        if not console.demo_mode() and task['state'] != 'cancelled':
            if result.get('review_ids'):
                from core.hitl import ApprovalQueue
                for aid in result['review_ids']:
                    review = ApprovalQueue(self.h.store).get(aid)
                    body += f"<article class=card><h3>Item review — {esc(review['status'])}</h3>" + render_payload(review['payload']['workflow_binding']['exact']['payload'])
                    exact = review['payload']['workflow_binding']['exact']['payload']
                    if (self.h.server.integrated and review['status'] == 'approved'
                            and exact.get('research_only_draft') and not task['paused']):
                        body += self.saas_handoff(task_id, exact)
                    if review['status'] == 'pending' and not task['paused']:
                        for verb, label in (('approve', 'Approve this exact item'), ('reject', 'Reject this item')):
                            body += f"<form method=post action='/workflows/{task_id}/{verb}{self.qs}'><input type=hidden name=approval_id value='{aid}'><button>{label}</button></form>"
                    body += '</article>'
            actions = []
            if task['paused']:
                actions = [('resume', 'Resume')]
            else:
                if task['state'] == 'waiting_for_review' and result.get('approval_id'):
                    actions += [('approve', 'Approve exact prepared result'), ('reject', 'Reject')]
                if task['state'] in ('queued', 'failed') or (task['state'] == 'partially_succeeded' and task['role'] == 'system_health'):
                    actions += [('prepare', 'Run / recheck')]
                if task['role'] == 'client_delivery' and task['state'] == 'succeeded' and task['input'].get('phase','scope') == 'scope' and result.get('prepared', {}).get('work_request'):
                    actions += [('request-work', 'Prepare work request')]
                if task['role'] == 'system_health' and task['state'] in ('succeeded','partially_succeeded'):
                    actions += [('request-diagnostics', 'Request Cortana diagnostics')]
                if task['state'] in ('waiting_for_device', 'waiting_for_auth', 'waiting_for_network', 'reconciling') or (task['state'] == 'partially_succeeded' and result.get('review_ids')):
                    actions += [('dispatch', 'Dispatch / reconcile reviewed action')]
                actions += [('pause', 'Pause')]
            actions += [('cancel', 'Cancel task')]
            body += '<div class=row>' + ''.join(f"<form method=post action='/workflows/{task_id}/{action}{self.qs}'><button>{label}</button></form>" for action, label in actions) + '</div>'
            body += f"<details><summary>Revise this task</summary><p>A revision invalidates pending approvals.</p><form method=post action='/workflows/{task_id}/revise{self.qs}'><input type=hidden name=revision value='{task['revision']}'><textarea name=inputs_json>{esc(json.dumps(task['input'], indent=2))}</textarea><button>Save new revision</button></form></details>"
        if task['state'] in ('succeeded', 'failed', 'cancelled') and not result.get('content_deleted'):
            body += f"<details><summary>Delete this task's saved content</summary><p>Removes this task's brief, drafts and review payloads. Keeps IDs and hashes to prevent replay. Shared contacts, source files, artifacts, commitment records and exported backups are retained.</p><form method=post action='/workflows/{task_id}/delete-content{self.qs}'><label>Enter {task_id} to confirm</label><input name=confirmation required><button>Delete saved task content</button></form></details>"
        events = self.h.store.query('SELECT kind,ts,payload_json FROM events WHERE thread_id=? ORDER BY ts', (task_id,))
        body += '<details><summary>Evidence and event history</summary><pre>' + esc(json.dumps(events, indent=2)) + '</pre></details>'
        self.respond(task['envelope']['intent'], body)

    def saas_handoff(self, task_id, draft):
        from core.search import public_web_url

        source = draft['source_ref']
        if not public_web_url(source):
            return ''
        esc = console.esc
        contact_id = draft['contact_id']
        outcome = self.h.store.kv_get('workflow_opportunities', contact_id, {})
        status = f"<p>Recorded outcome: {esc(outcome['status'])}</p>" if outcome else ''
        return f"""
        <p><a href='{esc(source)}' target='_blank' rel='noopener noreferrer'>Open the source discussion</a>.
        If community rules permit a reply, use the reviewed question above and record what happened.</p>
        {status}
        <form method=post action='/workflows/{task_id}/saas-outcome{self.qs}'>
        <input type=hidden name=contact_id value='{esc(contact_id)}'>
        <label>Observed outcome</label><select name=status>
        <option value=posted>Manually posted</option><option value=interested>Interested reply</option>
        <option value=disqualified>Disqualified</option><option value=opt_out>Opted out</option>
        </select>
        <label>Post or response link</label><input type=text name=source_ref required>
        <label>Exact evidence or reply quote</label><textarea name=quote required></textarea>
        <button>Record outcome</button></form>"""
