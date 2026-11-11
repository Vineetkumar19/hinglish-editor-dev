# Storylens Downloader — implementation and validation

Added Downloader to the main tool list and provided /downloader.html. Existing
feature cards remain title/purpose only. yt-dlp and FFmpeg are shown inside the
feature. No local LLM or GPU queue is required.

## Implemented

- YouTube video and Shorts links with 2160p (4K), 1440p (2K), 1080p and 720p caps.
- Instagram Reel/post and Pinterest video Pin links, including pin.it redirects,
  choose the best available source format.
- Video, audio only, or video plus separate audio. Audio exports are 48 kHz
  24-bit WAV or 320 kbps MP3. Compatible video is remuxed; other codecs are
  converted to H.264/AAC MP4 without resizing. Conversion is lossy and can take
  time, especially for 4K. Source resolution is never fabricated by upscaling.
- Actual output dimensions, media preview, Save video/audio, private range-aware
  downloads, recent jobs, cancellation and saved results.
- Separate video/audio FCP7 XML timelines for Premiere and Resolve; new CapCut
  video or audio projects through the existing editor handoff. Audio timelines
  contain no dummy video clips. Existing editor projects remain intact.
- Public single videos only; no browser-cookie access, playlists, live streams
  or private/login-only content. One active job, six-hour and 8 GB source limits.

## TDD and checks

The contract tests were written before implementation and first failed because
hinglish_app.downloader was absent. UI-model tests first failed because that
module was absent. Regression tests were added during development for the
library's successful-download limit exception and feature-scoped errors.
Initial test temp directories were inaccessible under the shell sandbox; the
runner now uses output/downloader-validation/tmp.

25 Python unit/integration/regression tests pass, including real FFmpeg/PyAV
processing and actual HTTP routes with a controlled transfer fixture. Four
JavaScript unit tests pass. Syntax checks and the app-style source lint pass.
Logs are in output/downloader-validation. A broader user-messages test run
exposed two assertions on existing Auto Captions redirect-only pages, which do
not load feedback.js; those unrelated pages were left unchanged. This is not
an all-project green test claim.

## Live application evidence

The user's links were entered through Storylens UI, not injected as fake success:

- YouTube R7UfRy2MDvo: 1280x720 MP4, approximately 170.9 seconds, plus a separate
  48 kHz stereo WAV. Source metadata listed all four requested resolutions.
  Full 1080p/1440p/2160p downloads were NOT repeated.
- Instagram DerN5wwviKy: 1080x1920 MP4, approximately 21.1 seconds, plus a
  separate 48 kHz stereo WAV. Audio playback advanced to its actual end in the
  running browser.
- Pinterest pin.it/3HHELRLrh: Rolex Luxury Branding, 720x1280 MP4, about 11.2 sec.
- Actual media delivery for all five produced assets returned matching file
  bytes, range status 206 and attachment headers.
- Premiere video and Resolve audio handoff dialogs reached their ready states.
  CapCut created the real installed-project files for Instagram audio: an audio
  track and audio material, with no video material. Existing projects preserved.
- Playback/import inside native Premiere, CapCut and Resolve was NOT verified.
  Premiere uses its existing XML import workflow; do not claim automatic native
  import merely because an editor package was prepared.

The initial YouTube run downloaded its source but stopped on yt-dlp's
max-downloads exception. During implementation that was corrected by checking
single-video metadata before download. Its failed history entry is retained.
An isolated validation instance was used while another chat was actively editing;
main port 8765 was reloaded only after the other job became idle. Publishing
stayed disabled and unrelated processes/jobs were not stopped.

## Final adversarial findings — deliberately NOT repaired

D1 — Medium: portrait Shorts quality uses height, not the short frame edge.
With 360x640, 720x1280 and 1080x1920 portrait formats and a 720p request, the
actual yt-dlp selector chose 360x640. Expected 720x1280. This can reduce Shorts
quality; the live landscape YouTube check does not cover this failure.

D2 — High: the private-network check is a DNS precheck, not a guard bound to the
actual connection and every redirect. In an isolated harmless test, a synthetic
public hostname changed resolution before connection and its response redirected
to our temporary loopback fixture. The fixture was reached. Expected private
address/redirect rejection. No owner service or sensitive data was accessed; an
exploit chain through a real YouTube/Instagram/Pinterest post is not established.
This is a confirmed transport-guard gap, not a claim of remote exploitation.

D3 — Low: refresh/reopening a saved result restores its output but does not
restore its URL, mode, quality or selected audio tab. The Instagram Video +
separate audio result reopened with an empty URL, Video mode and default quality.
Saved media stays intact, but the next download can use unintended defaults.

Findings and safe reproduction are saved in adversarial-findings.json,
restored-ui-state.json, and tools/audit_downloader.py. No fixes were made after
these final findings, per the owner's instruction. The known quality and security
gaps prevent a claim that the feature is fully validated or hardened.
