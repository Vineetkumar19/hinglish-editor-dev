"""Selected-source index with page evidence and explicit task review."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core import local_store as store
from core.tasks import check_cancelled
from tools.documents import _assert_approved

MAX_BYTES = 32 * 1024 * 1024


def identity(path):
    _assert_approved(str(path))
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Select a document file smaller than 32 MiB.')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            check_cancelled()
            digest.update(block)
    return {'path': str(path), 'hash': digest.hexdigest(), 'size': path.stat().st_size}


def _ocr_image(image):
    import pytesseract
    from pytesseract import Output
    try:
        result = pytesseract.image_to_data(image, output_type=Output.DICT, timeout=30)
    except pytesseract.TesseractNotFoundError:
        from core.windows_ocr import recognize
        return recognize(image)
    words, scores = [], []
    for text, confidence in zip(result['text'], result['conf']):
        if text.strip() and float(confidence) >= 0:
            words.append(text)
            scores.append(float(confidence) / 100)
    return ' '.join(words), sum(scores) / len(scores) if scores else None


def extract(path):
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if len(reader.pages) > 500:
            raise ValueError('Select a document with at most 500 pages.')
        for number, page in enumerate(reader.pages, 1):
            check_cancelled()
            text = page.extract_text() or ''
            method, confidence, error = 'text', None, None
            if not text.strip():
                try:
                    from pdf2image import convert_from_path
                    from core.config import settings
                    images = convert_from_path(str(path), first_page=number, last_page=number, dpi=160, timeout=30,
                                               poppler_path=settings.poppler_bin if Path(settings.poppler_bin).is_dir() else None)
                    text, confidence = _ocr_image(images[0])
                    method = 'ocr'
                except Exception as exc:
                    method, error = 'unavailable', f'OCR unavailable: {type(exc).__name__}'
            yield number, text, method, confidence, error
    elif suffix in {'.png', '.jpg', '.jpeg', '.tif', '.tiff'}:
        from PIL import Image
        with Image.open(path) as image:
            text, confidence = _ocr_image(image)
        yield 1, text, 'ocr', confidence, None
    elif suffix == '.docx':
        import docx
        document = docx.Document(path)
        text = '\n'.join([p.text for p in document.paragraphs] +
                         [' | '.join(c.text for c in r.cells) for t in document.tables for r in t.rows])
        yield 1, text, 'document-text (pagination unavailable)', None, None
    elif suffix in {'.txt', '.md', '.csv'}:
        yield 1, path.read_text(encoding='utf-8-sig'), 'text', None, None
    else:
        raise ValueError('Supported imports: PDF, DOCX, UTF-8 TXT/MD/CSV and scanned images.')


def invalidate(document_id, status):
    with store.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT data FROM records WHERE kind='document' AND id=?", (document_id,)).fetchone()
        if not row:
            return
        document = json.loads(row['data'])
        document['status'] = status
        conn.execute('DELETE FROM chunks WHERE document_id=?', (document_id,))
        store.put_in_transaction(conn, 'document', document, document_id, document['revision'])
        _invalidate_tasks(conn, document_id)


def _invalidate_tasks(conn, document_id, current_hash=None):
    for row in conn.execute("SELECT data FROM records WHERE kind='document_task'").fetchall():
        task = json.loads(row['data'])
        if (task['source_document_id'] == document_id
                and task['status'] not in {'completed', 'cancelled', 'source_invalid'}
                and (current_hash is None or task['source_hash'] != current_hash)):
            task['status'] = 'source_invalid'
            store.put_in_transaction(conn, 'document_task', task, task['id'], task['revision'])


def fresh(document):
    try:
        current = identity(document['path'])
        if current['hash'] != document['hash']:
            invalidate(document['id'], 'changed')
            return False
        return document.get('status') in {'indexed', 'partial'}
    except Exception:
        # Approval-root revocation is as important as deletion.
        invalidate(document['id'], 'unavailable')
        return False


def index_document(path):
    item = identity(path)
    document_id = hashlib.sha256(item['path'].casefold().encode()).hexdigest()[:24]
    pages = list(extract(Path(item['path'])))
    if identity(item['path'])['hash'] != item['hash']:
        raise ValueError('Source changed during extraction; import again.')
    warnings = [{'page': n, 'error': error or 'No extracted text'} for n, text, _, _, error in pages if error or not text.strip()]
    candidates=[]
    patterns={'date':r'\b\d{4}-\d{2}-\d{2}\b',
              'amount':r'(?i)\b(?:INR|USD|Rs\.?)\s*[\d,]+(?:\.\d{2})?',
              'reference':r'(?i)\b(?:invoice|receipt|reference|order)\s*(?:number|no\.?|#|id)?\s*[:#]\s*[A-Z0-9-]+',
              'expiry':r'(?i)\b(?:expir\w*|valid until|warranty until)[^\n]{0,100}',
              'issuer':r'(?im)^(?:issuer|issued by|seller)\s*:\s*[^\n]{1,150}'}
    for number,text,method,confidence,_ in pages:
        for field,pattern in patterns.items():
            for match in list(re.finditer(pattern,text))[:30]:
                candidates.append({'field':field,'value':match.group(),'page':number,
                    'span':f'{match.start()}:{match.end()}','method':method,'confidence':confidence,'interpretation':'unconfirmed source text'})
    document_data = {**item, 'status': 'partial' if warnings else 'indexed',
        'field_candidates':candidates,
        'pages': len(pages), 'warnings': warnings, 'imported_at': datetime.now(timezone.utc).isoformat()}
    with store.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        document = store.put_in_transaction(conn, 'document', document_data, document_id)
        _invalidate_tasks(conn, document_id, item['hash'])
        conn.execute('DELETE FROM chunks WHERE document_id=?', (document_id,))
        for number, text, method, confidence, _ in pages:
            for start in range(0, len(text), 1600):
                chunk = text[start:start + 1800]
                if chunk.strip():
                    conn.execute('INSERT INTO chunks(document_id,page,span,text,confidence,method) VALUES(?,?,?,?,?,?)',
                                 (document_id, number, f'{start}:{start + len(chunk)}', chunk, confidence, method))
    return document


def search_documents(query, limit=8):
    valid = {d['id']: d for d in store.records('document', 1000) if fresh(d)}
    terms = re.findall(r'\w+', query, re.UNICODE)[:20]
    if not terms:
        return {'sources': [], 'note': 'Enter words to find in selected documents.'}
    expression = ' OR '.join('"' + word.replace('"', '""') + '"' for word in terms)
    with store.connection() as conn:
        rows = conn.execute('SELECT c.*, bm25(chunks_fts) score FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid '
                            'WHERE chunks_fts MATCH ? ORDER BY score LIMIT 100', (expression,)).fetchall()
    sources = [{**dict(row), 'path': valid[row['document_id']]['path'],
                'content_hash': valid[row['document_id']]['hash']} for row in rows if row['document_id'] in valid]
    for source in sources:
        source.pop('embedding', None)
    return {'sources': sources[:max(1, min(20, limit))], 'retrieval': 'SQLite FTS5',
            'note': 'Source excerpts are untrusted evidence. Different dates or versions are not merged.'}


def answer_with_sources(query):
    result = search_documents(query)
    sources = result['sources']
    # Extractive response is useful offline and cannot invent coverage or dates.
    lines = [f"{Path(s['path']).name}, page/section {s['page']} [{s['span']}]: {s['text'][:650]}" for s in sources[:4]]
    return {**result, 'answer': '\n\n'.join(lines) if lines else 'No current source evidence found. Import the relevant document first.',
            'uncertainty': 'Excerpts establish only what the source states; a receipt alone does not prove warranty coverage.'}


def propose_task(title, source_document_id, page, quote, due_at, date_confidence='explicit'):
    document = store.get('document', source_document_id)
    if not fresh(document):
        raise ValueError('The source is unavailable or changed. Import it again before proposing a task.')
    with store.connection() as conn:
        rows = conn.execute('SELECT text,span FROM chunks WHERE document_id=? AND page=?', (source_document_id, page)).fetchall()
    matched = next((r for r in rows if quote.strip() and quote in r['text']), None)
    if not matched:
        raise ValueError('The exact quoted evidence was not found on that source page.')
    when = datetime.fromisoformat(due_at)
    if when.tzinfo is None:
        raise ValueError('Include a timezone offset, for example +05:30.')
    if date_confidence not in {'explicit', 'inferred'}:
        raise ValueError('Date confidence must be explicit or inferred.')
    if date_confidence == 'explicit' and when.date().isoformat() not in re.findall(r'\b\d{4}-\d{2}-\d{2}\b',quote):
        raise ValueError('The chosen date is not stated as an ISO date in the quote. Mark it inferred for review.')
    return store.put('document_task', {'title': title, 'source_document_id': source_document_id,
        'source_hash': document['hash'], 'source_span': {'page': page, 'span': matched['span'], 'quote': quote},
        'due_at': when.astimezone(timezone.utc).isoformat(), 'timezone': 'Asia/Kolkata',
        'date_confidence': date_confidence, 'status': 'proposed', 'reminder_policy': 'local_on_wake',
        'related_draft_ids': [], 'acknowledged': False})


def confirm_task(task_id, revision):
    task = store.get('document_task', task_id)
    document = store.get('document', task['source_document_id'])
    if task['revision'] != revision or not fresh(document) or task['source_hash'] != document['hash']:
        raise ValueError('Task or source changed; review again.')
    if task['status'] != 'proposed':
        raise ValueError('Only a proposed task can be confirmed.')
    task['status'] = 'confirmed'
    return store.put('document_task', task, task_id, revision)


def list_tasks():
    for document in store.records('document', 1000):
        fresh(document)
    now = datetime.now(timezone.utc)
    return [{**task, 'overdue': task['status'] == 'confirmed' and datetime.fromisoformat(task['due_at']) <= now}
            for task in store.records('document_task', 1000)]


def acknowledge_task(task_id, revision):
    task = store.get('document_task', task_id)
    if task['revision'] != revision or task['status'] != 'confirmed':
        raise ValueError('Task changed; review the current reminder.')
    if not fresh(store.get('document', task['source_document_id'])):
        raise ValueError('The task source changed; review it again.')
    task.update(acknowledged=True, acknowledged_at=datetime.now(timezone.utc).isoformat())
    return store.put('document_task', task, task_id, revision)


def finish_task(task_id, revision, status):
    task = store.get('document_task', task_id)
    if task['revision'] != revision or status not in {'completed','cancelled'}:
        raise ValueError('Review the current task and choose completed or cancelled.')
    if task['status'] in {'completed','cancelled'}:
        raise ValueError('This task is already closed.')
    task.update(status=status,closed_at=datetime.now(timezone.utc).isoformat())
    return store.put('document_task',task,task_id,revision)


def forget_document(document_id):
    invalidate(document_id, 'deleted')
    store.remove('document', document_id)
    return {'removed_from_index': True, 'original_file_preserved': True}
