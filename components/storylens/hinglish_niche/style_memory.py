"""Offline semantic retrieval for isolated documentary styles."""
from pathlib import Path
from functools import lru_cache
import json,os
import numpy as np
from .documentary import SETS
from .reference_dna import StyleDatabase


class StyleEmbedder:
    model_name = 'intfloat/multilingual-e5-small'

    def __init__(self,root):
        from hinglish_cut.model_storage import role
        selected = role(root, 'embedding')
        self.ollama = None
        if selected:
            from hinglish_cut.ollama_embeddings import OllamaEmbeddings
            self.model_name = selected['ollama_model']
            self.ollama = OllamaEmbeddings(root, self.model_name)
            return
        import torch
        from transformers import AutoModel,AutoTokenizer
        from hinglish_cut.backends import model_location
        torch.set_num_threads(2)
        location=model_location(self.model_name,Path(root)/'models',True)
        self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained(location,local_files_only=True)
        self.model=AutoModel.from_pretrained(location,local_files_only=True).eval()

    def encode(self,texts,query=False):
        if self.ollama is not None:
            return self.ollama.encode(texts,query=query)
        results=[]
        for start in range(0,len(texts),16):
            batch=self.tokenizer([('query: ' if query else 'passage: ')+t for t in texts[start:start+16]],
                padding=True,truncation=True,max_length=256,return_tensors='pt')
            with self.torch.inference_mode():
                hidden=self.model(**batch).last_hidden_state
                mask=batch['attention_mask'].unsqueeze(-1)
                pooled=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
                results.extend(self.torch.nn.functional.normalize(pooled,dim=1).numpy())
        return np.asarray(results,np.float32)


@lru_cache(maxsize=1)
def _embedder(root):
    return StyleEmbedder(root)


def search(root,style,query,limit=5,embedder=None,kinds=None):
    if style not in SETS:raise ValueError('Choose a saved documentary style.')
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        raise ValueError('Enter a short description of the edit you want.')
    path=Path(root)/'library/creator-profiles/editing-dna.sqlite3'
    if not path.is_file():return []
    db=StyleDatabase(path)
    count=max(1,min(int(limit),10))
    try:
        try:
            model=embedder or _embedder(str(Path(root).resolve()))
            rows=db.search_vector(style,model.encode([query],query=True)[0],count,kinds=kinds,model=getattr(model,'model_name',None))
            if rows:return rows
        except (OSError,ValueError,ImportError):
            pass
        return db.search_text(style,query,count,kinds=kinds)
    finally:db.close()


def planning_examples(root,query,purpose=None):
    from .profiles import CURRENT
    context=CURRENT.get() or {}
    if not context and os.environ.get('HINGLISH_CREATOR_CONTEXT_FILE'):
        context=json.loads(Path(os.environ['HINGLISH_CREATOR_CONTEXT_FILE']).read_text(encoding='utf-8'))
    if not context and os.environ.get('HINGLISH_CREATOR_CONTEXT'):
        context=json.loads(os.environ['HINGLISH_CREATOR_CONTEXT'])
    if context.get('profile')!='cricket':return []
    style=context.get('documentary_style')
    if style not in SETS:return []
    if not isinstance(query,str) or not query.strip():return []
    try:
        kinds={'sound': ['audio-window','sound-event-candidate','rhythm-region','continuous-motion-second',
                          'single-video-second','single-video-lesson','single-video-visual-review'],
               'motion': ['scene-evidence','reviewed-chapter','reviewed-pattern','approved-animation',
                          'transition-candidate','editing-pace','continuous-motion-second','brain-guidance',
                          'single-video-second','single-video-lesson','single-video-visual-review']}.get(purpose)
        rows=search(root,style,query[:1800],4,kinds=kinds) if kinds else search(root,style,query[:1800],4)
        if not rows and kinds:
            # Earlier style memories stored audio context within scene evidence.
            rows=search(root,style,query[:1800],4)
    except (OSError,ValueError,ImportError):
        # Optional style retrieval must not disable an existing editing tool if
        # a moved installation has not yet restored its local embedding weights.
        return []
    return [{'source':r['data'].get('source',r['source']),'start':r['start'],'end':r['end'],
             'usage':'analysis-only technique evidence; no reference frames, clips, audio or branding may be used in production',
             'reference':r['text'],'status':r['data'].get('status','measured reference'),
             **({'motion_measurements':r['data']['motion'],'audio_context':r['data'].get('audio',{})} if 'motion' in r['data'] else {})} for r in rows]
