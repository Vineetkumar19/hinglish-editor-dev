# Phase 2 and Clean+ validation

> **Superseded by the September 15 paragraph fix.** The earlier tests below
> did not validate the user's full six-paragraph / thirteen-video edit.
> The previous "12/12" claim is not evidence of reliable model judgments:
> deletion rules had overridden the model's explicit removal veto. The veto is
> now respected. See `PARAGRAPH-FIX-RESULTS.md` for the actual batch findings.

Validated locally on September 10, 2026, using the CPU configuration.

## Automated checks

- 64 regression tests passed.
- 12/12 explicit local-model safety cases passed after deterministic gates were applied.
- Cases cover paraphrases, changed numbers, negation, reversed participant roles,
  unrelated topics, incomplete retakes, lost details, hesitations, reactions, and commands.
- The original `hinglish_cut` source files remain byte-for-byte unchanged from the
  saved pre-Phase-1 baseline.

## Real footage: Phase 2

- Script idea: `Log mujhse sawal karte hain.`
- Actual speech: `Log mujhe poochhate hain.`
- The wording differs but the meaning match was accepted.
- Edited audio was transcribed again as `Log mujhe poochhate hain.` and passed
  the preservation check.
- A 1080x1920 Premiere timeline with one linked video clip and two linked audio
  channels was produced at:
  `output/phase2/20260910-231615-217756/timeline.xml`.

## Real footage: Clean+

- User clip `VID20260808003844.mp4` was processed end to end.
- Duration changed from 6.87 seconds to 3.30 seconds after silence removal.
- The output remained 1080x1920 at 30 fps, with working portable media links.

## Retake replay fixture

- Two nearby instances of real Hindi speech were analyzed as repeated takes.
- The first take was removed, the kept audio was transcribed again, and its text
  and meaning matched the expected remaining take.
- Output: `output/clean-plus/20260910-231914-133850/001/cleaned.mp4`.

## Limits kept visible in the product

- These checks reduce mistakes but do not guarantee perfect semantic editing.
- Bad ASR, ambiguous occurrences, names, facts, and uncertain alignment are sent
  to the review page.
- `oh`, `shh`, short emphasis, incomplete retakes, materially shorter attempts,
  and distant repeated topics are not automatically deleted.
- A filler omitted by Whisper cannot be safely found from text.
- Clean+ currently assumes one talking-head speaker. Overlapping podcast speakers
  and multi-camera synchronization are outside this phase.
- CPU behavior was validated. RTX 5070 behavior still requires that hardware.
