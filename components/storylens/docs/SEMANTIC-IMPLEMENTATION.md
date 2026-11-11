# Meaning-based assembly and Clean+

The new `hinglish_semantic` package shares only media decoding, audio assembly,
alignment, and XML helpers with the existing app. It does not load the old
Rapido-script-specific word corrections. It provides two separate modes.

## Matching

### Meaning repair (September 17)

`matching_backend: meaning` retrieves whole source phrases and compares their
intended message with a pinned local Qwen3 4B quantized model. It does not require
lexical overlap to approve a paraphrase. Sentence boundaries come from source
punctuation, long pauses and clause lead-ins, rather than matching arbitrary
word windows. Short emphatic chains stay together. An isolated script cue must
have a direct spoken occurrence; paragraph context cannot manufacture it.

The matcher keeps explicit changed-number/negation/protected-term guards and
the no-reused-words/frames sequence constraints. If an otherwise matched amount
is unclear in the transcript, its whole sentence may remain with a mandatory
listening flag. This is not a verified amount. Full phrase candidates preserve
meaning-bearing endings when the script uses another expression. Natural pacing
and XML/preview generation use the existing source-time cutting path.

The runtime binds only to loopback with a per-process key and is shut down after
use. Inference is local; no API subscription is required. Model/runtime revisions
and verdict prompts are included in cache keys. New downloads are pinned;
the runtime archive is checksum-checked. Clean+ continues on its separate path.

A Turbo speech recognizer was also evaluated independently without script
prompts. It worsened several names/English words in this batch and is **not**
the normal speech backend. Changing model size alone did not solve the problem.
The source transcriber remains Swift. This model comparison does not establish
40-minute editing accuracy or RTX 5070 performance.

### Previous paragraph coverage path (September 15)

`Run Phase 2.bat` now uses `coverage.py` and `paragraph_export.py`.
Every paragraph retains its identity but is assembled from separate clauses,
potentially spanning several source files. Compact original word windows,
Hinglish spelling variants and spoken number normalization supply coverage
evidence; E5 reranks those candidates. Nearby complete later attempts replace
earlier ones. Global selection prevents source-word and source-frame reuse.
Padding respects neighboring selections. VAD removes pauses inside the chosen
windows; recognized, aligned hesitation tokens can be removed with protected
neighbor boundaries. This does not detect fillers omitted by ASR.

Meaning-only E5 candidates remain review alternatives when wording evidence is
insufficient. They do not auto-approve missing content. The small Qwen judge is
no longer used to certify Phase 2 paragraph coverage; it falsely accepted
partial and unrelated passages in the user's failed run. Clean+ still uses it,
including its explicit removal veto, alongside deterministic guards.

September 16 correction: sub-frame gaps/overlaps between neighboring words use
one nearest-frame cut boundary; grossly overlapping ASR intervals cannot both
be scheduled. Questions keep their short negative answers, quoted sentence
endings split correctly, and short/scripted repetitions are not superseded as
retakes. Missing clauses may retain a bounded source passage that immediately
adjoins a selected word range in the same paragraph and source, with sufficient
retrieval evidence and no fact conflict or reused frames. These retain the
explicit `unverified_context_passage` status in the project and review page;
inclusion is not evidence that the spoken meaning matches. Unanchored guesses
remain missing. The terminal and report distinguish both states.

Each paragraph is transcribed again after editing. This is a fallible consistency
check, not independent proof of speech or meaning accuracy. Results always need
listening review. Exports are `EDITED_SEQUENCE.xml` plus `preview.mp4`, generated
from the same frame cuts. The XML retains full-quality media; preview is smaller.

### Legacy implementation (old saved projects only)

The following older path remains for compatibility with saved review projects;
it is not the default paragraph matcher and must not be used as an accuracy claim.

1. VAD and ASR run locally. Nearby speech regions are grouped for transcription
   context; original speech intervals remain available for silence removal.
   Analysis windows and completed transcripts are cached independently of scripts.
2. Sentence/pause units retain media IDs, word indices, original seconds, and
   alignment uncertainty. Up to four adjoining units form larger candidates.
3. Multilingual E5 embeddings retrieve candidates. A small lexical signal breaks
   ties. Both alternate endpoints and distinct occurrences remain available.
4. Qwen checks complete meaning and contradictions. Numeric/negative/protected
   term concerns cannot be overridden by a high embedding score. Failed JSON,
   unavailable models and low-confidence judgments do not count as approval.
5. A beam search selects the whole sequence, enforcing no source-word reuse.
   Automatic mode enforces forward progress for one source. Ambiguous global
   solutions are flagged with timestamped alternatives.
6. Actual edited audio is transcribed and checked again. Doubtful edits regain
   pauses and stay in a draft. Only a fully checked sequence gets timeline.xml.

## Cleanup

VAD plus all aligned/unaligned transcript spans protect speech. Candidate fillers
need both recognizable hesitation text and usable acoustic alignment; expressive
sounds are review-only. Nearby retakes use lexical and embedding candidates,
but deletion also requires context, complete replacement, fact checks and a
local verifier. Replay checks can cancel a proposed deletion. No adjacent
non-target word may overlap a deleted frame range.

Manual review produces a small choices file. Applying it validates the generated
project schema, accepts only listed candidates/removals, creates a fresh output,
and reruns frame bounds/overlap checks. User choices never execute shell code.

## Models and references

- [Multilingual E5 small](https://huggingface.co/intfloat/multilingual-e5-small):
  MIT model card; Transformers mean pooling and normalized query embeddings.
  The card's scores are not Hinglish-specific accuracy evidence.
- [Qwen2.5 1.5B Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct):
  Apache-2.0 model card; local structured-output verifier. Small-model judgments
  are fallible and are not treated as guaranteed semantic equivalence.
- Existing Oriserve Whisper, MMS alignment, Silero VAD and PyAV integrations
  provide the local speech/media implementation without new runtime libraries.

Validation cases and measured outcomes are written under validation. No
subscription readiness, podcast diarization, exhaustive filler recognition,
or 100% semantic accuracy is claimed by this implementation.
