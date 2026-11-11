"""Two bounded retrieval workers, sharing one screenshot analysis and verifier."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import re


def heading_query(row,quoted=True):
    # This is visible title text, not a generated completion or source metadata.
    title=' '.join(str(row.get('caption') or '').split())
    title=title.replace('…',' ').replace('...',' ').replace('"',' ').strip(' .')
    title=' '.join(title.split())[:300]
    if not title or len(re.findall(r'\w+',title))<2:return ''
    publisher=' '.join(str(row.get('publisher') or '').replace('"',' ').split())[:100]
    if publisher.casefold() in ('unknown','unreadable','none','n/a'):publisher=''
    return ' '.join(part for part in ((f'"{title}"' if quoted else title),publisher) if part)


def search_candidates(finder,row,cancel=None):
    """Yield independent image-search batches; a failed worker cannot erase another.

    Workers retrieve URLs only. The caller still downloads securely and verifies
    actual pixels with the existing geometric matcher before accepting a photo.
    """
    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Photo collection cancelled; saved photos are kept.')
    check_cancel()
    queries=[('visual',str(row.get('query') or '').strip()),('heading',heading_query(row))]
    queries=[(agent,query) for agent,query in queries if query]
    if not queries:return
    def run(agent,query):
        check_cancel()
        try:
            candidates=[{**item,'search_agent':agent,'search_query':query}
                        for item in finder.images(query,limit=24)]
            return {'agent':agent,'query':query,'candidates':candidates,'error':None}
        except InterruptedError:raise
        except Exception as error:
            return {'agent':agent,'query':query,'candidates':[],'error':str(error)[:700]}
    executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='photo-search')
    pending={executor.submit(run,agent,query) for agent,query in queries}
    try:
        while pending:
            check_cancel()
            done,pending=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for future in done:
                check_cancel()
                yield future.result()
    finally:
        for future in pending:future.cancel()
        # Existing provider timeouts bound any already-started request.
        executor.shutdown(wait=True,cancel_futures=True)
