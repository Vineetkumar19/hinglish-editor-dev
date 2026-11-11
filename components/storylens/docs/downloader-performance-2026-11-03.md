# Downloader performance correction

The existing queue and editor-ready H.264/AAC contract remain. Native fragmented
transfers use six concurrent requests rather than two. The source format selector
and resolution cap are unchanged: no upscale, quality downgrade or new codec
preference was introduced. Direct nonfragmented downloads still use yt-dlp's
existing transport; its YouTube extractor already supplies HTTP chunk settings.

Progress hooks check cancellation and size on every invocation but persist
progress at most twice per second. Missing fragments abort after bounded retries
instead of silently skipping material. Compatible tracks merge to MP4 when
possible, with MKV fallback. An already compatible MP4 receives an internal
hardlink, or a bounded cancellable copy when linking is unavailable, avoiding
another full FFmpeg read/write pass. Final saved files remain separate copies.
Incompatible codecs retain the existing GPU H.264 conversion.

Job timings separate download/probe, per-kind preparation, saving and total time.
Download timing includes metadata lookup, any merge and section processing; it
does not isolate internet transfer alone. Retry timings describe the current
attempt, which may reuse a saved source.

TDD failures reproduced the two-connection setting and redundant MP4 media pass.
Focused unit/media checks and localhost HTTP integration passed. Real installed
yt-dlp transport against identical controlled delayed fragments measured 1.514s
with two connections versus 0.568s with six; final bytes and SHA256 matched.
This is a latency-controlled benchmark, not a YouTube speed guarantee.

The idle main service was reloaded with the same command and publishing worker
still disabled. Its actual HTTP downloader downloaded and auto-saved a two-second
excerpt of the owner's previously supplied YouTube link in 3.539s, with 0.012s
video preparation. It produced 1280x720 H.264/AAC. No full 10–15-minute 4K transfer,
new native editor import, other-platform check or model invocation was performed.

Remaining limits: direct HTTP transfers do not gain six parallel ranges; provider
throttling/network/disk can dominate; incompatible 4K conversion still takes time;
the prior DNS/redirect pinning finding remains outside this performance change.
Evidence: `output/downloader-performance-20261103/status.json`.
