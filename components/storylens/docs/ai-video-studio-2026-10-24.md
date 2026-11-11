# AI Video studio — 24 October 2026

The owner requested three demonstrations: prompt-to-video, reference-guided
generation, and motion / 3D. They explicitly requested that other chats keep
using the GPU and that these jobs wait in the shared queue. Do not stop other
jobs or bypass `gpu_lock` to accelerate this demonstration.

## Implemented paths

- Prompt to video: existing local Qwen planning, optional Z-Image first frame,
  Wan 2.2 footage, local evaluator and review / timeline handoff.
- Reference guided: public YouTube metadata through the installed Agent Reach
  backend, or a local video; ReelMimic measurements and actual local Vision frame
  reading guide the new scene plan. Source material is untrusted reference data.
  The reference is not installed as shared selected guidance. This is approximate
  guidance, not training or a promise of exact reconstruction.
- Motion / 3D: delegates to the existing bounded GSAP / Hyperframes recipes,
  including Three.js / ThreeUI orbital depth. It bypasses the Wan model check.
  Rendered 3D is a video layer; no native editable 3D scene is promised in an NLE.

The coordinator is `hinglish_aivideo/studio.py`. Existing caption renderers and
saved profiles remain outside this change. No OpenCut work or model download was
started. The isolated demonstration service is port 8786 with publishing disabled.

## Validation record so far

- Public Agent Reach search succeeded; receipt:
  `output/ai-video-studio-evidence/agent-reach-live.json`.
- Actual missing-reference UI check showed the shared plain-language error,
  kept the script, and allowed adding the reference afterward. Screenshot:
  `output/ai-video-studio-evidence/missing-reference-live.png`.
- Prompt-to-video first attempt failed during Wan loading with a Windows access
  violation. Model files were complete; a zero-byte abandoned tokenizer download
  marker was preserved in the evidence directory. Compact transformer loading
  and complete raw worker logs were added. The repaired loading path requires
  a live retry; low memory is a suspected cause, not a confirmed diagnosis.
- First motion attempt failed because the structured schema allowed a title
  count of ten while rendering accepted six. The real model selected eight.
  Title, number and item schema limits now match the runtime checks.
- Twenty-five focused tests passed (AI Video studio, shared AI generation,
  creative motion). Python compilation and JavaScript syntax checks passed.
  These checks do not establish live generation quality.
- Three short jobs were submitted through the visible Storylens application
  after the repairs. They wait behind existing GPU work and run serially.
  The first completed orbital sample decoded all 155 frames at 640×360, but
  sampled frame inspection rejected its incomplete second title. A scoped
  preserve-script setting, balanced long-line pagination and full short-line
  validation were added for AI Video motion. The corrected render is queued.
  Browser playback was blocked by the in-app browser local-file policy. Native
  editor handoffs remain unverified.

- Reference ingestion attempted a second GPU reservation inside its already
  reserved app job. It now reuses the parent reservation; direct ingestion still
  acquires its own. Retrying missing Vision keeps cached measurements and owner
  guidance. Regression checks cover both reservation modes and retry recovery.
- A rapid prompt submission exposed an empty style before the asynchronous style
  menu loaded. The default is now retained, and the UI waits for method support
  before submission. Older services receive a clear restart message rather than
  silently ignoring the new method.
- Latest motion controls were inspected live, including the 360p label and hiding
  footage-only fields. Screenshot: motion-controls-live.png in the evidence folder.
- A follow-up in this same chat checks the existing jobs every five minutes and
  stays quiet while their queued states are unchanged. Automation identifier:
  `finish-the-three-ai-video-demonstrations`. The three existing test tabs were
  retained for continuation; do not resubmit active jobs.

## Boundaries

Only public YouTube URLs and local reference videos are supported by the new
reader. An installed tool does not imply access to every platform or private
account. Public search success is separate from visual video understanding.
Full-quality generation, image-to-video, native editor playback and exact
reference fidelity need their own live evidence. Keep incomplete checks explicit.

## Live continuation, approximately 02:07–02:15 IST

The queued jobs advanced. This is still initial implementation validation, not
the final adversarial review. No other job or service was stopped.

- **Confirmed motion break:** with the eleven-word demonstration, the local
  model selected the first six words of its second sentence and an empty footer.
  Expected: every source word in reading order. Actual: runtime validation
  correctly rejected the incomplete line. Impact: no usable new motion demo.
  Evidence: `output/motion/20261024-020557-e6fc78/001-script/creative-plan.json`.
- **Confirmed reference break:** the configured local Vision call returned an
  empty object. Expected: a complete measured-frame style description. Actual:
  reference generation stopped before claiming visual understanding. Impact:
  no reference-guided footage yet. Evidence: the saved `visual_reading: {}` in
  `library/reelmimic/aivideo/4d9edf6f06a9707cd581f03a/profile.json`.
  The style-reading request did not use the shared request configuration; this
  is a confirmed omission, but the original empty answer's cause is unproven.
- **Initial-loop repairs:** two new regression tests were written and observed
  failing before implementation. Scripted motion now asks for a bounded headline
  word count; code binds the source prefix and every remaining support word to
  complete slots. Independent lossy word spans no longer drive these scripted
  title recipes. Reference description now uses the configured request settings,
  rejects incomplete descriptions and records a per-reference Vision receipt.
  Existing cached measurements and owner guidance are retained.
- **Checks:** both new tests passed after implementation; all 27 focused AI
  Video/shared generation/creative motion tests passed. These are supplementary
  unit and component integration checks, not acceptance of model output.
- The stopped motion and reference demos were each resubmitted once through
  their existing visible Storylens tabs. The prompt-to-video job was active at
  Wan text-encoder loading and was left running. No duplicate active job was
  submitted. Retry screenshots: `motion-retry-0200.png` and
  `reference-retry-0200.png` under the evidence directory.
- Live validation of these newest repairs, actual generated footage, full
  playback and native editor handoffs remain pending. Final adversarial review
  has not begun; any findings from that later review must be reported without
  silently fixing them, per the latest owner instruction.

## Next live continuation — motion result and Windows loader failure

- The corrected AI Video orbital run completed through Storylens:
  `output/motion/20261024-021204-ee8a96/001-script/MOTION_GRAPHICS.mp4`.
  Its saved model-selected hierarchy and deterministic word slots retain all
  eleven source words. The entire 155-frame file decoded at 640×360 / 30 fps;
  opening and two second-scene frames were inspected and show both the headline
  and `clear story.` support text. The sphere moves between sampled frames.
  This is sampled visual/file verification, not full native-editor playback.
  The running editor showed the completed result; screenshot:
  `output/ai-video-studio-evidence/motion-complete-live.png`.
- Reference frame reading now finished with a complete local-model description.
  The actual receipt records model `storylens-planner:9b-q6`, four source frames,
  thinking disabled, `done_reason: stop` and 109 output tokens. It is stored at
  `library/reelmimic/aivideo/4d9edf6f06a9707cd581f03a/vision-reading.json`;
  the generated job retained `reference-analysis.json`. This verifies ingestion
  and a model response; fidelity remains approximate and no reference-guided
  video has completed yet.
- **Confirmed footage break:** both prompt and reference jobs crashed while
  loading Wan transformer shards. Expected: load weights and generate a clip.
  Actual: Windows access violation 3221225477; the raw stack identifies
  `safetensors.torch.load_file` / `torch.storage.__getitem__`. Impact: both
  footage demonstrations remain unavailable. Prompt receipt:
  `output/aivideo/20261024-020653-489c5c/001-script/jobs-clips-1a38.worker.log`;
  reference receipt:
  `output/aivideo/20261024-021308-8ed246/001-script/jobs-clips-c95a.worker.log`.
  This narrows the failing operation; underlying memory/OS cause is unproven.
- A new Windows loader regression test was written and observed failing first.
  The worker now requests Diffusers' supported `disable_mmap=True` for compact
  Wan transformer loading on Windows. That test and all 28 focused tests passed.
  The stopped prompt and reference jobs were each retried once in the existing
  application, through the shared queue. Their new real loading/render results
  are pending. No running job was stopped or duplicated.

## Prompt-to-video result — next continuation

- The non-mapped Windows loading path completed a real Storylens run:
  `output/aivideo/20261024-021528-682a16/001-script/videos/m01-a294.mp4`.
  The local planner selected the paper-boat scene, Wan generated the clip and the
  local evaluator reviewed it. Its saved project labels method `generative`,
  quality `preview`, first-frame mode off. All 49 frames decoded at 832×480 /
  24 fps (2.0417 seconds). Four frames were extracted; opening, middle and final
  samples were visually inspected and show the requested paper boat, water and
  sunrise. The boat changes position between sampled frames.
- **Quality limitation:** the local evaluator scored 7/10 but rejected the exact
  camera pan/follow instruction. This is a generated preview, not acceptance of
  exact camera motion or final quality. No extra render was submitted to hide
  that finding. Full playback/native handoff remain unverified.
- **Confirmed presentation finding, preserved for final review:** after that
  evaluator rejection, the main editor still displayed a green quality-check
  pass at 96/100. Expected: the failed content/motion check should be clear to
  the person reviewing quality. Actual: its failure is in the project/review,
  while the main screen shows a pass. Impact: file/rule success can be mistaken
  for complete visual instruction compliance. Evidence: `aivideo-project.json`
  in the run folder and `output/ai-video-studio-evidence/prompt-complete-live.png`.
  This finding has not been fixed; report it rather than silently changing
  acceptance policy during final testing.
- The existing reference-guided retry advanced after this run. It was left
  running; no duplicate was submitted. The completed motion demo was retained.

## Final demonstration and review status

- Reference-guided generation finished through the running Storylens app:
  `output/aivideo/20261024-022312-b04d3e/001-script/videos/m01-a0f0.mp4`.
  All 49 frames decoded at 832×480 / 24 fps (2.0417 seconds). Opening, middle
  and final sampled frames show herbs in a planter; later frames have strong
  green colour bleeding and malformed leaf/edge shapes. The actual local
  evaluator rejected the result at 3/10. The source-reference hash, measured
  palette/movement, local Vision description and method `reference` remain in
  this job's project and reference-analysis receipt. It is a real generated
  preview, not an accepted-quality reference recreation.
- All three requested routes have now produced real application outputs.
  This does not mean all outputs passed visual acceptance or that the entire
  application is production-ready. The prompt's camera compliance was flagged,
  and the reference preview's visible artifacts are confirmed.
- Final safe reviewer/security checks ran after generation. Seventeen checks
  passed: unsupported/local/spoofed reference URLs stop before reader execution;
  missing local files do not invoke analysis; invalid methods/styles/quality/
  counts/options are rejected; 600 script lengths and Unicode preserve words;
  injected report text stays inert; the running service rejects unauthenticated
  job reads and foreign-origin bridge requests. These checks used isolated
  scratch files and local read-only requests. No model/render/publish task was
  started for them. Detailed record:
  `output/ai-video-studio-evidence/final-review.json`.
- Two actual final live input checks also passed in the separate controls tab:
  blank script and missing reference show recoverable plain-language errors
  without creating a render. Their screenshots are `final-empty-script.png`
  and `final-missing-reference.png` in the evidence directory.
- Unit/component checks remain 28/28 passing. The three real generation runs
  are application integration evidence; frame decoding and sampled inspection
  are separate evidence. Full playback, full-quality generation, first-frame /
  image-to-video, public YouTube download-to-render, and Premiere/CapCut handoff
  were not verified.

### Breaking points preserved, not repaired in final review

- **Quality presentation:** run either footage demo with its evaluator enabled.
  Expected: failed visual/content checks are clear on the main result. Actual:
  the local verdict is rejected (prompt 7/10; reference 3/10), yet the editor
  reports a green 96/100 pass. Impact: a technical/file pass can be mistaken for
  visual acceptance. Evidence: both saved aivideo-project.json verdicts, the
  main-screen screenshots and final-review.json. This is confirmed.
- **Reference preview quality:** the demonstrated sunny-herb-garden request
  should produce clean foliage and geometry. Actual: later frames show green
  smearing and malformed edges, also flagged by the evaluator. Impact: this
  preview is unsuitable as a finished video. Evidence: the actual reference
  MP4 and reference-frame-048.png. This is confirmed for preview settings; it
  does not establish full-quality settings' result.
- **Camera compliance limit:** the paper-boat clip was generated, but the local
  evaluator rejected the exact pan/follow direction. Sampled inspection confirms
  boat motion, not precise camera matching. Treat this as a flagged limitation,
  not a proven universal model failure.

Per the latest owner rule, final-review findings were recorded without fixes or
extra renders. The follow-up stops after delivering these reviewed outcomes;
further quality-policy/visual repairs require the owner's subsequent request.
