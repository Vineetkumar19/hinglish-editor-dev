# Meaning matcher repair

Goal: arrange actual spoken ideas in script order despite paraphrasing, keeping
complete utterances and original timing. No words are generated into the audio.
Decision owner: user, with explicit listening review for uncertain/factual changes.

Current failure snapshot: output/phase2/20260917-090817-355252 (Rapido batch).
Known errors: lexical windows truncate "alag struggle" when the script instead
says "psychological warfare"; one-word Har matches unrelated bahar; word windows
swallow preceding price speech; number ASR mishears sixty; script-only Sun is absent.

Experiment: independent stronger ASR, multilingual utterance retrieval, then
local semantic comparison of whole bounded utterances. Script is an outline:
equivalent phrasing and rhetorical changes are permitted, invented factual
claims and reversed actions are not. Do not silently insert a merely adjacent
passage as an accepted match. Split source candidates at actual utterance edges,
not into arbitrary subsets that remove the paraphrased meaning-bearing words.

Evidence gates before default promotion: contrast equivalent vs reversed or
changed numbers, the full active batch plus targeted failure cases from the two
historical batches, source timing / no-reuse / natural
pacing checks, cache restart checks, and a large-transcript retrieval measurement.
Synthetic duration/scale checks are not long-video editing-quality validation.
No claim of 40–50 minute readiness without representative long-footage review.

Constraints: local CPU today, no paid/editor APIs, preserve original cutter,
inputs and earlier exports; retain natural pacing and portable Premiere XML.
Model scores and software test counts are not accuracy percentages.
