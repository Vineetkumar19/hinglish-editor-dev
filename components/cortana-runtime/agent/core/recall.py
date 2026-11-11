"""Relevance ranking for long-term memory (the retrieval half of RAG).

Design choice worth stating: this uses lexical scoring (TF-IDF-ish token
overlap), not vector embeddings. Embeddings would need a second model
resident in RAM alongside the 3B chat model on a 24GB/4GB-VRAM laptop,
plus an embedding call on every single turn — real latency and memory
cost for a personal fact store that will realistically hold hundreds of
short facts, not millions of documents. At this scale lexical matching is
both faster and, for "what's my sister's birthday", about as accurate.

If the fact store ever grows past a few thousand entries, swapping this
module for an embedding index is a contained change: retrieve_relevant()
is the only function the rest of the app calls.
"""

import math
import re

# Words too common to carry meaning — they'd match everything.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "i",
    "me", "my", "mine", "you", "your", "he", "she", "it", "we", "they",
    "of", "to", "in", "on", "at", "for", "with", "and", "or", "but", "if",
    "do", "does", "did", "can", "could", "will", "would", "should", "what",
    "when", "where", "who", "how", "why", "this", "that", "these", "those",
    "have", "has", "had", "please", "tell", "about", "from", "get", "got",
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9']+", (text or "").lower())
    out = []
    for w in words:
        # Normalize possessives and stray quotes so a query for "amit"
        # matches a stored "Amit's number is ...". Without this the two
        # are different tokens and only scrape a weak prefix match.
        w = w.replace("'s", "").strip("'")
        if w and w not in STOPWORDS and len(w) > 1:
            out.append(w)
    return out


def _score(query_tokens: list[str], fact_tokens: list[str], doc_freq: dict, total_docs: int) -> float:
    if not query_tokens or not fact_tokens:
        return 0.0
    fact_set = set(fact_tokens)
    score = 0.0
    for qt in set(query_tokens):
        if qt in fact_set:
            # An exact word match is always worth a full point; the IDF
            # term on top just rewards rarer words. Relying on IDF alone
            # meant that with only a handful of facts stored, every term
            # was "common" and even a perfect match scored near zero.
            df = doc_freq.get(qt, 1)
            score += 1.0 + math.log(1 + total_docs / df)
        else:
            # Partial credit for prefix matches ("birthday" vs "birthdays").
            for ft in fact_set:
                if len(qt) >= 4 and (ft.startswith(qt) or qt.startswith(ft)):
                    score += 0.4
                    break
    # Normalize a little so long facts don't win purely by being long.
    return score / (1 + math.log(1 + len(fact_set)))


def retrieve_relevant(query: str, facts: list[dict], top_k: int = 5, min_score: float = 0.5) -> list[dict]:
    """Returns the most relevant facts for this query, best first.

    `facts` is a list of {"id", "content", ...} as returned by db.all_facts().
    Facts scoring below min_score are dropped rather than padded in — an
    irrelevant "memory" injected into the prompt is worse than none.
    """
    query_tokens = tokenize(query)
    if not query_tokens or not facts:
        return []

    tokenized = [(f, tokenize(f.get("content", ""))) for f in facts]

    doc_freq: dict[str, int] = {}
    for _f, toks in tokenized:
        for t in set(toks):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    total_docs = max(1, len(tokenized))

    scored = []
    for fact, toks in tokenized:
        s = _score(query_tokens, toks, doc_freq, total_docs)
        if s >= min_score:
            scored.append((s, fact))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [f for _s, f in scored[:top_k]]
