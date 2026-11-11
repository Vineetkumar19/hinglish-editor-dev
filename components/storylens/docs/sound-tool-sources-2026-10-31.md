# Local sound tool sources (31 October 2026)

These are isolated tool checkouts. The Storylens adapters below add evidence to Sound Design; Qwen remains the sound and timeline decision maker.

| Tool | Local source | Pinned commit | License / scope |
| --- | --- | --- | --- |
| Clipwing Real SFX | `tools/reference-repositories/clipwing-skills/skills/real-sfx` | `edbefcbc3474869e6cc1e8a7ca583b0efd0dab7e` | README labels scripts MIT; bundled uisfx recordings CC0. User sound packs retain their own licenses. |
| Openverse | `tools/reference-repositories/openverse` | `fbfce911cbd34a676762c5df85a0ac0305391d5c` | MIT application code. Sparse checkout contains `api` and `documentation`; retrieved audio has per-file licenses and attribution requirements. |
| Earshot | `tools/reference-repositories/earshot` | `591fa3e028032e6dce56620a20e932e35667e8d8` | MIT application code. CLAP/AST model weights have separate licenses and are not part of the checkout. |

Clipwing Real SFX is also installed as a Codex skill at `C:\Users\Vineet Kumar\.codex\skills\real-sfx`, with Storylens's existing `library/owner-sound-packs/sfx` configured as its main recording library. Storylens calls its measured picture-moment detector for supported video inputs and passes those anchors to Qwen as optional timing evidence. The existing sound recordings were neither moved nor changed.

The Real SFX setup check found FFmpeg, FFprobe, Python, its bundled UI pack, and an index of 1,282 usable Storylens recordings (from 1,366 scanned audio files). The check used `tools/reelmimic/bin` on PATH; a normal shell may need that same FFmpeg/FFprobe directory on PATH.

Earshot 0.4.0 uses an isolated `.venv` in its checkout. `earshot doctor --fetch` downloaded the pinned CLAP and AST model files and reported healthy dependencies. A direct local CLAP ranking distinguished a motorcycle sound from a cinematic water-themed effect; both were weak/poor matches for a literal accelerating engine, which is useful evidence for Qwen rather than a veto. Storylens gives its shortlisted sound recordings advisory Earshot descriptions before Qwen selects. Openverse's public audio API is connected as a bounded fallback for missing local sounds. Only CC0/CC-BY recordings on approved direct media hosts are eligible, with attribution and source metadata retained. An online API response has not yet been verified from this machine; the local HTTP request timed out. The local Openverse checkout is source reference, not an offline media catalog.

Runtime adapters: `hinglish_sound/tool_bridge.py`, `tools/sound_tools/earshot_rank_batch.py`, and `hinglish_sound/online_sources.py`. The Qwen reference instructions are in `hinglish_app/knowledge/sound_reference_studies.json`. Per-job receipts in `sound-decisions.json` and `sound-plan.json` report which tools actually ran. Existing short-form keyword folders, Qwen draft timeline, human review, and editor exports remain the handoff.

## Real Storylens trial

The July 9 rainy travel reel was submitted through the running Storylens Sound Design UI with music off and the short-form keyword-folder workflow. The job at `output/sound/20261031-135217-8487a9/001-vineet_2919_2026-07-09_12-29-09_39372793` completed in about 24 minutes. It indexed 2,224 effects, found 16 Clipwing picture moments, scanned nine visual intervals, gave Qwen Earshot evidence for 42 recordings across eight slates, and let Qwen place 21 effects. The result has a 26.6-second H.264/AAC preview, a draft XML timeline, 19 keyword folders, and an export ZIP. Its technical audio check passed; listening approval and native editor playback remain unverified. Openverse was not invoked because local matches existed.

The run exposed creative and speed limits: Qwen overrode the initial serious palette with “comedic” after over-weighting creator references, and inserted generic clicks despite the outdoor footage. The palette prompt was tightened after this job had loaded, so that correction has not been checked in a new live run. The generic-click behavior and roughly 24-minute runtime remain findings for the owner to assess. The online fallback remains unverified against a live Openverse response. No second model rejected Qwen's selections. Focused unit checks: 33 passed; the live job is the application integration evidence, not proof of subjective sound quality.
