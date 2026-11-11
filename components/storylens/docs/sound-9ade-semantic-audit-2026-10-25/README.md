# Actual local Sound 9ade: semantic/timing audit

**Result: genuine local inference and concrete alternatives; physical sound-design
acceptance FAILED / remains pending.** `ready` means review candidates exist,
not that the water/sliding request is covered. No corrected plan, winner, source
substitution or runtime edit was supplied during this audit.

Job: `9ade0cafcfa6`. Saved output:
`output/sound-recommendations/20261025-064938-f348668ccc`.
`result.json` and actual HTTP receipts record Ollama loopback 0.40.5, Meaning 14B,
Vision 9B-Q6 and Embedding 8B-Q6 with digests, `test_factory_used=false`,
`semantic_checkpoint_resumed=false`, `rendered=false`, `native_imported=false`.
`local_agent_acceptance=false` is correctly retained. The active profile was
**Gaming**, not the previous General profile; no profile was switched here.
The script is the recovered ASR text, not a verified exact owner script.

## What is actually offered

| Planned group | Proposed time | Actual alternative evidence / coverage |
| --- | --- | --- |
| Music, neutral | 0–10s | Three instrumental Cylinder tracks; listener labels include ambient/documentary/tense. Full duration covered structurally; joyful/comedic suitability not established. |
| `bright_sunny_day` ambience | 0–5s | Five options led by Funny melody audio logo, Festive melody audio, Horror bell cartoon transition. Their saved listener labels are sparkle/success/notification/ding/riser. These do not establish water/environment coverage. |
| Click on ASR `kolo` | 3.94–4.14s | Five click/switch/metal-lock options. Anchored to a word, not a measured physical contact. Weak narrative reason; no demonstrated water/sliding relevance. |
| Sweep on `ye` | 4.40–4.70s | Five synthetic swoosh/transition options. Its name Futuristic slide does not make it physical waterslide Foley. No measured visual contact/movement alignment was established. |
| Tension before `imejineshan` | 4.48–6.48s | Five drone/suspense/string options. A developing two-second sound is possible, but emotional fit and true rise/peak alignment are unverified. |
| Click on `to` | 7.68–7.83s | Five game/UI/mouse-click options. Word timing exists; emphasizing this function word is not evidence of a motivated physical action. |

There are 28 alternatives across one music and five SFX groups, **not 28 stacked
sounds or a finished mix**. Two groups are short clicks; one sweep is .3s.
The five-second bed and two-second suspense show the model can author longer
durations, but the actual scene-related sounds are missing. No physical Foley
group survives. No sustained water layer covers 5–10s; no sliding/splash layer
is offered. No accepted joyful chime/comic-sting group survives either.

## The model DID propose physical sounds; validation dropped them

Actual raw model reply `receipts/0027-model-http-response.json` contains seven
scene layers. Only `bright_sunny_day` survives into `local-analysis.json`:

- Walking, water splashing, running and sliding are authored as `type=foley`,
  `role=texture`. Current `layers.ROLES` reserves `texture` for ambience;
  `visual_interval` Foley permits `detail` or `contact`. The rows are rejected.
- The 5–10s water ambience uses `offset=5.0`, interpreted as a relative offset
  even though its event already begins at 5s. Bed offset must be zero. It is
  rejected, rather than becoming a valid continuous bed.
- Sliding also has that invalid offset. The additional cute detail on the
  sliding event is rejected because `visual_interval` permits Foley only.

Actual speech reply `receipts/0032-model-http-response.json` contains eleven
layers; only four survive. Several 1–1.5s chimes and comic stings use unsupported
type/role pairs (`cute/awkward` with `contact`) or invalid offsets; an ending
chime would also exceed the timeline. A water-like `whoosh` tail is invalid and
is not legitimate physical evidence from a speech anchor. Rejecting invalid
rows is appropriate; the missing coverage is not repaired or prominently
reported before returning a generic five-group review.

This is more specific than “Qwen cannot think of water sounds”: it named them,
but its structured output violated the accepted contract and the remaining
choices fail the requested physical sound coverage.

## Existing frame evidence, viewed without extracting/rendering new frames

The two saved input PNG blobs were inspected in place:
`input-blobs/5dab87dff0b0e90509ac3ac61e1a6635f10692e410fdcddd88ecf47d5a52d7d3.bin`
and `input-blobs/e5c0a0c3ac3c0c8345119179e125c2c93ba6b339db48e18ce184acb200e64fde.bin`.

The first contact sheet shows a water-play structure, people and visible falling/
spraying water in some tiles. The second shows the slide/rider in early tiles,
then views over chutes and a later graphic/cut. It does not independently prove
one uninterrupted rider descent throughout 5–10s. Wet-concrete footsteps,
running, specific clothing/surface timbre and exact splash contacts are not
confirmed from these sparse low-resolution frames. Vision's .95 confidence is
a model assertion, not an audited probability or an audio/listening receipt.
Its all-frames event intervals and approximately .417s sampling uncertainty
must not become millisecond contact claims.

## Structural checks that passed, and their limits

All 28 saved candidate IDs reproduce from the frozen ID function. Positive
source windows fit saved available bounds; source/timeline durations match;
candidate times fit their groups and the 10s timeline. Ranks are descending
and source/score pairs match the actual prepared query snapshots. All paths
are registered in the saved inventory, exist, and current file sizes equal the
saved source sizes. The source-window selections retain the explicit measured-
energy/semantic-contact-unverified qualification. No out-of-bounds candidate was
found by these checks.

These are saved-artifact/pure-function/file-stat checks, **not independent source
hash verification, audio decoding, excerpt listening, mix balance, native import
or waveform/contact validation**. Current source bytes and credit contents were
not rehashed/revalidated here. Model-derived listener facts/ranks are not proof
that a candidate sounds right. The ranker's top choice was not adopted manually.

Saved stage durations total **431.842s (7m12s)**, including 272.533s in planning.
This sum excludes unmeasured queue/setup time and is not end-to-end native or
fresh-video latency. No new timings/inference were generated by this audit.

## Newly evidenced final-review findings — frozen, not repaired

- **Coverage silently lost after invalid layer output:** reproduce by comparing
  the two actual raw layer replies above with the five retained moments. Expected:
  covered observed actions or an explicit incomplete-coverage outcome. Actual:
  zero Foley groups, generic remainder still `ready`. Impact: the owner's central
  water/sliding requirement is not met despite successful model calls.
- **Non-audible ambience intent admits tonal effects:** follow `bright_sunny_day`
  from Vision through scene plan to manifest. Expected: evidence naming an
  audible environmental source or no physical ambience recommendation. Actual:
  melody/notification/horror-transition alternatives labelled ambience. The
  unknown-subject allowance in `relevance.source_matches` does not establish an
  environmental identity. Saved names/listener metadata demonstrate the mismatch;
  actual perceptual judgment still requires listening.
- **Long ambience label loses confidence during restoration:** the 5–10s raw
  ambience label is truncated to 160 characters by `events.normalize`; `_plan`
  then matches that shortened string against the full raw label. The saved
  measured event `519debe9a0a3` has no confidence although its observation is .95.
  Expected: preserve the matching observation's evidence. Actual: a later physical
  row can fail the confidence gate. This is an additional latent route, not the
  observed bed's first rejection cause (its offset already fails).
- **Scene interpretation overstates continuous motion:** Vision declares the
  whole second sheet to be continuous sliding with a detailed acoustic mechanism.
  Existing sampled frames show changing views/cut content. Expected: intervals
  and uncertainty tied to what is actually visible. Impact: unreliable physical
  event scope even before sound composition. No precise corrected interval was
  invented by this audit.

Music-tone mismatch remains an **unresolved creative risk** rather than a proven
listening failure: the palette is corrected from serious to comedic, but the
music mood remains neutral and three neutral/tense candidates are offered. The
music intent describes ambient park sounds instead of a musical brief. Neither
funny-library alternatives nor actual joyful phrase suitability were auditioned
here. Speech-anchor confidence 1.0 denotes timing/evidence handling, not reliable
ASR spelling or semantic relevance; raw scores range as low as .334.

No source/runtime edits, corrected plans, new inference, network, scans, GPU,
renders or native actions occurred. Only this documentation/audit JSON was
written. Existing protected defects remain unchanged. The suite owns actual
listening and native operator checks; global readiness and creative acceptance
must remain pending.
