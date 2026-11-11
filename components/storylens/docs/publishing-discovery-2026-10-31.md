# Publishing discovery and packaging

This adds a review step to the existing Prepare and Post pipeline. It does not
replace the account, upload, scheduling, receipt or duplicate-prevention engines.

## Workflow

1. Choose Cricket or Gaming and a finished video, Highlights or Shorts request.
2. Leave **SEO & thumbnail review** enabled for the new preparation. Live YouTube
   search suggestions can be turned off independently.
3. The existing local transcription, source-excerpt and publishing writer run.
   The same configured publishing model then proposes a primary search phrase,
   viewer intent, three title angles (search, browse, hybrid), a revised
   description/tags and a complementary thumbnail brief.
4. Expand **SEO & thumbnail review**. Use a title or description/tags separately,
   then **Save reviewed text**. Suggestions never silently replace prepared text.
5. For Long/Highlights, **Open brief in Thumbnail Studio** prefills a new draft
   and backs up the previous local draft. Generation remains the user's choice.
   Select the finished image path in Prepare and Post, then **Save thumbnail
   selection**. The exact file identity is saved before the first upload.
6. Review the normal platform fields, audience and synthetic-content declaration.
   Choose Post now or Schedule through the existing controls when ready.

Shorts/Reels retain the owner's no-uploaded-cover rule. Instagram retains its
existing source-grounded maximum ten prose words plus relevant hashtags.

## What was adapted

- [youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill):
  `yt-seo` query intent and description opening; `yt-package` complementary
  title/thumbnail promises, readable wording and truncation checks.
- [claude-youtube](https://github.com/AgriciDaniel/claude-youtube): metadata and
  thumbnail briefing, accurate source-specific copy and intentional title angles.
- `claude-seo` remains a separate website SEO reference. Website schema,
  sitemaps and technical website audits are not YouTube ranking features.

The installed sources and licenses remain unchanged. These are adapted workflow
instructions and deterministic checks, not newly trained model weights. Fixed
title-number requirements and heuristic CTR/ranking scores were not adopted.

## Boundaries and recovery

Only an explicitly enabled new preparation adds automatic review inference. Old saved
preparations are not regenerated automatically. **Refresh review** can add or retry
suggestions for an idle, unsubmitted prepared video without changing its copy or
rerunning ASR/media work. Newly created full workflows save their review
settings; older workflows do not acquire them on continuation. New direct
assistant preparations also enable the review. Automated posting continues to
use its prepared copy until the owner explicitly applies a suggestion.

One bounded public autocomplete request is cached for 24 hours, with query,
timestamp, source and availability status. The local model proposes a concise
search phrase from the video; returned suggestions feed one bounded refinement.
This sends a search phrase to Google's YouTube suggestions
endpoint; no video file or complete transcript is sent. These are autocomplete
observations, not keyword volumes, competition scores or promised rankings.

The optional review gets up to two attempts and an independent source-grounding
critique. All transcript chunks remain represented through the existing checked
source-excerpt pipeline. A failed review keeps baseline metadata, paired Instagram
copy and saved media; its plain-language message and technical details remain
visible. Owner-approved description links are reapplied by the existing policy.

Titles/descriptions use the existing authenticated metadata edit route. Thumbnail
changes require an idle, prepared non-Short draft with no submitted jobs; source
identity and image type are checked. Once submitted, the upload binding is frozen.

No new model downloads, global model/context changes, automatic thumbnails,
analytics/account connections, platform experiments or publishing permissions
are introduced.

## Validation

Evidence and the isolated real-app result are in
`output/publishing-discovery-20261031`. The validation application has its own
preparation store and no production credentials or queued publications. Native
workers use the real configured model/runtime and production GPU lock. Tests are
supporting evidence; the status file records actual UI/model checks and remaining
deployment or platform limits.
