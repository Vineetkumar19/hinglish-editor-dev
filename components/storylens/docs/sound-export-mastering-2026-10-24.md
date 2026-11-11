Editable soundtrack mastering correction — 24 October 2026

The actual E7 export exposed a defect that the previous preview-only peak check
missed: summing the raw dialogue/music/effect stems produced +5.18 dBFS and 30,729
samples over full scale, while the rendered preview was safely limited.

Sound Design now applies one common normalization/limiter gain curve to every
editable component at its actual timeline samples. Individual PCM components
also share a safe cancellation bound. Canonical plan.stems paths refer to these
mastered files, including for already-imported/older editor adapters. Raw
measurement stems remain under plan.stems.analysis for voice-relative evaluation;
they must never be the default editor export. Source clips, cue choices, role
levels, timing, references and owner feedback remain intact.

The new sound.editor_ceiling and sound.editor_match checks sum the real editable
files and compare them with the rendered master. Missing/silent exported effects
still fail sound.audible; intentional common master attenuation must not trigger
louder retries. The hot-overlap regression demonstrates the original >0 dBFS
failure and checks reconstructed PCM matching. Existing mix/role tests remain.

Storylens CLI --refresh-export rebuilds a saved sound plan without new model
selection or adding positive owner feedback. It preserves saved kept/removals
and separated voice. The first E7 render is retained in
output/sound-new-samples-2026-10-24/before-mastering-fix. Its current 54-effect
result was rebuilt: editable sum -1.9999 dBFS and maximum PCM difference .0001221.
Quality checks passed. Old CapCut project copies remain preserved; new handoffs
must use the corrected plan/metadata and a fresh project key.

Owner now explicitly requests the next demonstration on either e2(1).mp4 or
e5 zomato.mp4. Zomato was chosen and submitted through Storylens as job
e1d6749b1a89 on port 8876, with High density, auto style and source music removal.
Its request/status live in output/sound-zomato-review-2026-10-24.
Do not reopen Premiere for testing: the owner requests CapCut only because of
RAM pressure. Other Storylens jobs remain running.
