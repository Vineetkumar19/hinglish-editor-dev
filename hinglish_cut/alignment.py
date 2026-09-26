"""CTC Viterbi alignment for bounded utterances, including repeated labels."""
import numpy as np
from .model import Word


def ctc_blank(vocabulary,padding_id):
    return vocabulary.get('<blank>',padding_id)


def ctc_path(log_probs, labels, blank=0):
    log_probs=np.asarray(log_probs,dtype=np.float32)
    if log_probs.ndim!=2 or not labels or not np.isfinite(log_probs).all():
        raise ValueError('Empty or invalid CTC input')
    if blank in labels or min(labels)<0 or max(labels)>=log_probs.shape[1]:
        raise ValueError('Unsupported CTC labels')
    t_count=len(log_probs)
    if t_count<len(labels)+sum(a==b for a,b in zip(labels,labels[1:])):
        raise ValueError('Not enough acoustic frames for this transcript')
    states=np.full(2*len(labels)+1,blank,dtype=np.int32)
    states[1::2]=labels
    n=len(states)
    skip=np.zeros(n,dtype=bool)
    skip[2:]=(states[2:]!=blank)&(states[2:]!=states[:-2])
    prev=np.full(n,-np.inf,dtype=np.float32)
    prev[0]=log_probs[0,blank]; prev[1]=log_probs[0,labels[0]]
    back=np.zeros((t_count,n),dtype=np.uint8)
    for t in range(1,t_count):
        one=np.concatenate(([-np.inf],prev[:-1]))
        two=np.concatenate(([-np.inf,-np.inf],prev[:-2]))
        two[~skip]=-np.inf
        choices=np.stack((prev,one,two))
        moves=np.argmax(choices,axis=0)
        prev=choices[moves,np.arange(n)]+log_probs[t,states]
        back[t]=moves
    state=n-1 if prev[-1]>=prev[-2] else n-2
    if not np.isfinite(prev[state]):
        raise ValueError('No complete CTC alignment')
    path=np.empty(t_count,dtype=np.int32)
    for t in range(t_count-1,-1,-1):
        path[t]=state
        state-=int(back[t,state])
    spans=[]
    for i,label in enumerate(labels):
        hits=np.flatnonzero(path==2*i+1)
        if not len(hits):
            raise ValueError('CTC skipped a transcript character')
        spans.append((int(hits[0]),int(hits[-1])+1,float(np.exp(log_probs[hits,label].mean()))))
    return spans


def align_tokens(log_probs, roman_words, originals, vocabulary, blank, stride):
    labels=[]; spans=[]
    if len(roman_words)!=len(originals):
        raise ValueError('Romanization changed token mapping')
    for word in roman_words:
        chars=[c for c in word.lower() if c.isalnum()]
        if not chars or any(c not in vocabulary for c in chars):
            raise ValueError(f'Unalignable token: {word}')
        start=len(labels)
        labels.extend(vocabulary[c] for c in chars)
        spans.append((start,len(labels)))
    aligned=ctc_path(log_probs,labels,blank)
    return [Word(originals[i],aligned[a][0]*stride,aligned[b-1][1]*stride,
                 sum(x[2] for x in aligned[a:b])/(b-a)) for i,(a,b) in enumerate(spans)]
