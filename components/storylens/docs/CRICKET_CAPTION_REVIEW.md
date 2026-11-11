# Local cricket caption review

Storylens supplies its local speech and language-model workflow with spelling
references in `hinglish_captions/cricket_vocabulary.json`. The references cover
IPL team names, historical team names, common international and IPL players,
and cricket terms. The file records its official IPL, ICC and MCC sources.
It is a spelling reference, not an exhaustive player registry or a match-results
database. Historical names such as Delhi Daredevils remain valid.

The local model evaluates candidate corrections against the surrounding
transcript. Saved examples supplement its knowledge; they do not unconditionally
replace text. Candidate IDs, exact original words and span boundaries are
validated before applying a correction. Overlapping choices must be resolved
by the local model. Correct names, adjacent Hindi words and valid singular or
plural terms are preserved.

Roman Hinglish stays Roman Hinglish. Numeric words and ordinals use digits.
Malformed scores require corroboration from a second local speech model;
historical cricket knowledge cannot authorize a guessed score. Unresolved
malformed scores stop rendering for review.

Short headings have a seven-word maximum and a separate local name-spelling
review. Corrected selected captions feed the publishing-copy transcript.
Original recognition words and timing remain in the editable project.

The normal Storylens command “repair the saved captions and headings” rechecks
the original speech and rebuilds only changed layers. An explicit request to
resume the publishing workflow can then return the revised exports to the
same assistant-owned pipeline. Repair alone does not publish.

Saved `caption-review-plan.json`, `caption-decisions/`, `caption_review` and
`title_review` provide evidence of the local model's decisions. This is
application-level memory and validation, not model weight training. It reduces
recognition errors but cannot guarantee that every spoken name is identified.
