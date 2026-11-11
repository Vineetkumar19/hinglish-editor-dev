# Storylens Beat Studio

Beat Studio has **two independent actions**, available in the Premiere Pro panel
and the Resolve Studio window. The Desktop editor has a Beat Studio page for
local analysis and exporting marker/effect timing plans.

## 1. Detect & mark beats

In Premiere, select exactly **one music clip on an audio track**, then click
**1. Detect & mark beats**. In Resolve Studio, choose the music's audio track
number and its clip number in timeline order, then use the same action.

The detector reads that clip's source in/out range and timeline placement. It
places sequence/timeline markers at the detected attacks, rounded to the nearest
timeline video frame. It does not cut your footage, change the song or apply
effects during detection. Normal-speed music is the supported plugin workflow;
reverse and variable-speed music should be rendered to a new music file first.

| Setting | Meaning |
| --- | --- |
| Strong | More detected musical attacks |
| Medium | Approximately half as many; balances detail with available clips |
| Light | Approximately one fifth; prominent attacks with fewer markers |
| Maximum markers | Optional upper limit matching your clip budget, e.g. 25 |
| Auto-detect | Optional polling of the chosen/selected music; defaults off |

These are **density** settings, not volume controls. A 50-attack fixture produces
50 / 25 / 10 markers respectively. Actual music counts vary. The maximum is a
cap: the detector never invents beats to fill a quota. Music with syncopation,
vocals or no strong percussion needs listening review. This is local transient
analysis, not guaranteed bar/downbeat detection or a generative AI model.

Auto-detect observes a selected music clip in Premiere, or the configured track
and clip slot in Resolve. It checks roughly every 1–2 seconds and analyzes in the
background; it is not an instantaneous live-audio monitor. Resolve versions
without the script's UI timer require **Refresh progress**. Effects never run
automatically, even with auto-detect enabled.

Changing music placement while analysis runs invalidates the result. Detect
again after changing the sequence, frame rate, music trim or placement. Existing
user markers are preserved; previous Storylens beat markers are replaced. Resolve
cannot stack a second marker at the same frame, so occupied user positions are
reported and skipped.

## 2. Apply effects to beats

After detection, click **2. Apply effects to beats** separately. Choose:

- **Punch zoom** or **Smooth zoom**.
- Zoom amount: **1–20%**, default **8%**.
- Target video track: default **V1**. Other tracks are left alone.

The action duplicates the sequence/timeline and adds native zoom keyframes at
the retained marker times. The zoom reaches its peak on the beat. Close pulses
and pulses that cannot fit inside a shot are skipped and counted. Existing
animated Premiere Scale controls and existing Resolve Fusion compositions are
skipped, preserving their animation. Empty target tracks produce no pulses.
The original sequence/timeline remains intact. A host failure can leave a partial
duplicate; it is reported rather than treated as a completed edit.

Premiere uses its intrinsic Motion Scale control; Resolve adds a Transform in a
new Fusion composition. Premiere retimed clips are skipped. Resolve effects on
retimed or compound/Fusion clips need host-specific visual validation; use
normal-speed source clips for this first implementation. Native editability is
different from a rendered export: these actions do not produce an MP4.

Project checkpoints are saved and checked before/after host mutations. Premiere
CEP writes sequence project copies beside the saved project in **Storylens Beat
Backups**. UXP saves project copies in its plugin data folder. Resolve exports
`.drp` snapshots to `output/beats/project-backups`. Save your Premiere project
before using Beat Studio. UXP needs local-file access for these backups.

## Effect packs

No proprietary preset, plugin, MOGRT or Fusion pack has been imported, analyzed,
redistributed or executed. Built-in zoom pulses work without buying a pack.
Adding a supplied pack later needs a separate adapter for its native format,
installed plugin dependencies and intended usage. A visual example helps judge
its appearance; a preset alone does not reliably explain where it belongs.
Arbitrary Premiere `.prfpset` files are not interchangeable with Resolve effects.

## Local files and availability

- Editor page: **Beat Studio** in the local editor's tool list.
- Per-analysis files: `output/beats/<analysis-id>/beat-plan.json`, `markers.csv`.
- `effect-plan.json` is created only by the second action.
- Browser-added music is copied into `output/beats/music`; plugin music is read
  directly from its existing local path. Nothing is uploaded to a cloud service.
- Analysis is serialized with other local editing work to reduce laptop load.
- One selected range is limited to one hour; supported music formats include
  WAV, MP3, FLAC, M4A, AAC, OGG, AIF/AIFF and embedded MP4/MOV audio.
- Frame timing supports fractional rates such as 30000/1001 and 60000/1001.
- Analysis results remain on disk. After restarting the bridge or losing a UI
  session, analyze again before applying effects.

Restart the local editor after updating the source. Existing installed editor
panels also need updating and the host needs restarting. The source installer
is `Install Editor Plugins.bat`; it is a development installer, not a signed
commercial release. The packaged UXP panel needs reloading in UXP Developer Tool.
After Effects is not a target of this feature.

## Validation boundary

Automated checks exercise actual WAV decoding, known attack positions, silence,
stereo, trimming, timeline offsets, fractional FPS, density subsets, clip caps,
upload validation, authenticated APIs, license enforcement and host contracts.
Host mocks verify marker ownership, timeline duplication and keyframe placement.
They do not establish that a particular installed Premiere/Resolve build renders
the desired visual result. Live editor acceptance and viewing/auditioning the
saved project remain necessary before calling this a production-tested plugin.

Implementation references: [Adobe UXP markers](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/markers),
[Adobe UXP component parameters](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/componentparam),
[Premiere public ExtendScript sample](https://github.com/Adobe-CEP/Samples/blob/master/PProPanel/jsx/PPRO/Premiere.jsx),
[Blackmagic Fusion scripting reference](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf).
