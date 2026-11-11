from collections import Counter
from .text import tokens, similarity

NEGATIONS={'nahi','nahin','na','mat','not','never','no','without','nobody','nothing','नहीं','मत'}


def compare_text(expected, actual, settings):
    a=tokens(expected,settings.aliases)
    b=tokens(actual,settings.aliases)
    # Ordered token edit distance remains useful as one signal, never a semantic proof.
    prev=list(range(len(b)+1))
    for i,word in enumerate(a,1):
        curr=[i]
        for j,other in enumerate(b,1):
            curr.append(min(prev[j]+1,curr[j-1]+1,prev[j-1]+1-similarity(word,other)))
        prev=curr
    coverage=max(0,1-prev[-1]/max(len(a),len(b),1))
    issues=[]
    if coverage<settings.coverage_threshold:
        issues.append('text_mismatch')
    if Counter(x for x in a if x in NEGATIONS)!=Counter(x for x in b if x in NEGATIONS):
        issues.append('negation_changed')
    if Counter(x for x in a if any(c.isdigit() for c in x))!=Counter(x for x in b if any(c.isdigit() for c in x)):
        issues.append('numbers_changed')
    for term in settings.important_terms:
        term_tokens=tokens(term,settings.aliases)
        def present(seq):
            return any(seq[i:i+len(term_tokens)]==term_tokens for i in range(len(seq)-len(term_tokens)+1))
        if term_tokens and present(a) and not present(b):
            issues.append('important_term_missing:'+term)
    if not b:
        issues.append('empty_transcript')
    return {'coverage':round(coverage,4),'issues':issues}
