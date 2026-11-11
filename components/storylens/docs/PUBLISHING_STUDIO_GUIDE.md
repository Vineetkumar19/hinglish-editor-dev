# Publishing Studio — folder to YouTube, Shorts and Instagram

Built for Hinglish Editor on 4 October 2026. Open the editor and choose **Publishing Studio** in the top bar.

## What is implemented

- One folder for finished long YouTube videos, one for finished Shorts shared to both platforms, one for YouTube thumbnails.
- Exact filename matching. `Mumbai Indians Journey.mp4` matches `Mumbai Indians Journey.png`.
- A command field that understands `Upload Mumbai Indians Journey on YouTube` and the exact filename.
- Proper English generation for all YouTube titles and descriptions (including Shorts), Instagram Reel captions, tags and hashtags, regardless of the spoken language. This permanent rule has priority over saved references and style feedback. A separate final translation/copy-editing pass rewrites generated metadata in English without receiving the older style references.
- Local transcript-based title, YouTube description, tags and Instagram caption generation. It reuses the project's Qwen brain. A matching `.txt` file supplies a script/transcript; otherwise the existing speech engine transcribes the video.
- Optional local Qwen vision analysis reads visible thumbnail words and design. It cannot establish facts about the video. Missing vision models do not prevent transcript-based preparation.
- Reuse of Long to Shorts: find hook moments, keep complete thoughts, render portrait MP4 clips with captions, and draft their metadata. Eight is an editable target, not a promise that every source contains eight good clips.
- A persistent SQLite queue. Every generated Short gets a shared YouTube/Instagram target date, one clip per day at 7:00 PM India time by default. Multiple batches append to the existing calendar.
- Review/edit metadata before authorizing a batch. Editing an unstarted item returns it to draft. Authorization binds the item to the connected account and explicit audience/synthetic-media declarations.
- Official YouTube resumable uploads, custom long-video thumbnails and native scheduled publication.
- Official Instagram Login account validation, Reel container creation, processing checks and publication.
- Optional automatic S3 staging for Instagram. It uses configured AWS credentials and a private bucket with a signed read URL, or an existing HTTPS video URL supplied in the sidecar.
- Browser notifications while the Publishing Studio page is open, plus durable receipt messages and links in the dashboard.
- Encrypted account tokens using Windows DPAPI. Tokens stay in `cache/publisher/*.dpapi` and are excluded from the dashboard.
- One worker per project. Atomic claims, content hashes and saved remote IDs guard against accidental duplicate uploads. An uncertain network outcome or interrupted upload is held for review instead of automatically reposted.

## Example folder

```text
E:\remove silence\publishing\
  long-youtube\
    Mumbai Indians Journey.mp4
    Mumbai Indians Journey.txt          (optional transcript)
    Mumbai Indians Journey.publish.json (optional creator metadata)
  thumbnails-youtube\
    Mumbai Indians Journey.png
  shorts-both\
    MI comeback.mp4
    MI comeback.txt                    (optional transcript)
```

You may choose another folder in Publishing Studio. **Save & create folders** makes these three subfolders.
Use finished MP4 exports. The scanner waits at least ten seconds after the file was last modified; the worker hashes the approved content again before uploading.
Generated clips stay in the existing `output/shorts/<run>/...` folder and are queued directly. You do not need to copy them into `shorts-both`.

## First-time account setup

Run `Setup Publishing.bat` to install the optional official Google and AWS clients. This setup does not install large AI models. The existing editing models provide the local brain.

### YouTube

1. Create/select a Google Cloud project and enable YouTube Data API v3.
2. Configure the OAuth consent screen for your own account. Create a **Desktop app** OAuth client and download its JSON file. Keep it outside source control.
3. In Publishing Studio, enter that JSON path and click **Sign in with Google**. Select your intended channel in Google's sign-in screen.
4. The tool requests upload and read-only account permissions. It displays the channel name; every authorized job is bound to that channel ID.
5. Use private visibility for the first real upload test. Public API uploads from a new unaudited project are restricted to private by YouTube. Public automation requires the platform's compliance audit; OAuth sign-in alone does not remove that restriction.
6. Mark **My YouTube API project is approved for public uploads** only after this restriction has actually been lifted. This checkbox is a configuration declaration, not a verification of Google's audit result.
7. The channel must have access to the desired upload/thumbnail features. Google OAuth test-mode token lifetime can affect unattended use; configure the app appropriately and reconnect if needed.

### Instagram

1. Use a **Creator or Business** professional Instagram account. The personal-account type is not supported by this publishing integration.
2. Create a Meta app for **Instagram API with Instagram Login**. For your own development account, configure the required app role/tester access. A public multi-user app needs the applicable Meta review/access requirements.
3. Obtain a token with `instagram_business_basic` and `instagram_business_content_publish` for that account. Instagram Login does not require a linked Facebook Page.
4. Enter the Instagram professional account ID and token in Publishing Studio. The tool verifies the account and encrypts the token under your Windows user.
5. Tokens expire. This first version does not implement an Instagram OAuth callback or unattended token refresh. Reconnect when Meta requires it. YouTube has an implemented interactive OAuth connection; Instagram currently uses a manually obtained official token.
6. Configure media staging as below. Publication needs both account access and reachable media.

Do not share credentials or tokens in chat. Use the app's connection controls and platform sign-in pages.

## Instagram media hosting

This implementation uses Meta's URL-based media ingestion. A local `E:\...` path cannot serve as `video_url`.

**Automatic option:** create an AWS S3 bucket, configure least-privilege local AWS credentials, and enter the bucket and region in Publishing Studio. The worker stages the approved clip at its due time, then gives Meta a signed HTTPS read URL valid for 24 hours. It saves the object key and container ID as it proceeds.

Use a bucket lifecycle rule for the `hinglish-publisher/` prefix to expire objects after seven days. The app does not delete cloud objects or configure the lifecycle automatically. Storage and transfer charges depend on your cloud provider. A signed URL avoids requiring a permanently public bucket.

**Existing hosting option:** supply a publicly reachable HTTPS URL beside your clip:

```json
{
  "video_url": "https://your-media-host.example/mi-comeback.mp4"
}
```

Save this as `MI comeback.publish.json` next to `MI comeback.mp4` before preparing. The URL must serve that same approved video and remain valid through Meta's processing. The current app cannot prove that an external URL serves identical bytes; use the automatic staging option when that assurance matters.

## Daily operation

1. Finish your edit and export the MP4. Save the thumbnail with the same base name.
2. Put them in `long-youtube` and `thumbnails-youtube`.
3. Type `Upload Mumbai Indians Journey on YouTube` in Publishing Studio.
4. Enable **Also turn this long video into daily Shorts** if wanted. Add correct names/facts to creator notes or place your transcript beside the source.
5. Click **Prepare upload & daily clips**. Local speech, brain and rendering work happen one preparation job at a time within this publisher. GPU-heavy editing jobs elsewhere in the app are not yet globally coordinated; avoid running those concurrently with preparation.
6. Use **Review generated clip** in the queue to open the existing Long to Shorts review page and inspect the clips before authorizing them. The source file is not moved or deleted.
7. Review the draft title, description, caption, account and dates. Choose the audience and realistic synthetic-media declaration. Select the intended posts and click **Authorize selected posts** once for the batch.
8. Enable the worker in settings. The long upload starts promptly. YouTube Shorts upload ahead and receive scheduled dates; Instagram Reel publication starts at the due date.
9. Check the receipts. `uploaded_private`, `processing`, `scheduled` and `published` are separate states. A scheduled upload is not described as already public.

The app's main window can be minimized. Keep the computer awake and online for Instagram. YouTube continues its server-side schedules when your computer is off after the uploads are complete.

The two platforms share a target time, but simultaneous publication to the exact second is not guaranteed. Network speed, Meta processing and YouTube processing can introduce delays.

The app does not constantly auto-publish everything dropped into a folder. Folder discovery is refreshed in the dashboard, while a named preparation command and a scoped batch authorization control what goes live. This prevents a half-finished export from being treated as a publication command.

## Offline/restart behaviour

- Queue and authorization survive restarts.
- Unstarted posts retain their target dates. Overdue Instagram items run after the worker returns online; the worker does not silently discard them.
- An in-progress upload interrupted by shutdown becomes `needs_review`. Check the saved remote ID and the platform's Studio/dashboard before taking further action. This version intentionally has no blind retry button for ambiguous publications.
- A disconnected account or missing hosting setup becomes `blocked`; correct setup and authorize the unstarted item again.
- Pausing the worker prevents new claims. It does not cancel an upload already underway or cancel a schedule already saved on YouTube.
- Browser notifications need the page open and browser permission. The durable dashboard receipts remain available even if browser notifications are unavailable. Phone/Telegram/email delivery is not implemented.

`Run Publishing Worker.bat` starts a lightweight queue-only worker. Do not run it simultaneously with the editor's publisher for the same root; the lock prevents that. You can configure Windows Task Scheduler yourself to run the worker at sign-in. The app does not currently install an operating-system scheduled task or a server that remains online when the laptop is off.

## Creator-supplied metadata

To reuse your own already-English title/captions without loading an LLM, declare the metadata language in the sidecar:

```json
{
  "metadata_language": "en",
  "metadata": {
    "title": "Mumbai Indians: The Journey Behind the Comeback",
    "description": "Your actual video summary and relevant context.",
    "instagram_caption": "Your own caption. #MumbaiIndians #Cricket #IPL",
    "tags": ["Mumbai Indians", "IPL", "cricket"]
  }
}
```

The file is named `Mumbai Indians Journey.publish.json` beside the video. Include `video_url` in the same object if you use existing hosting. Local generation writes natural, relevant metadata; it does not perform current keyword research or promise search rankings.

## Learning from your corrections

Publishing Studio now has **Your learning memory**. Choose the area (titles, descriptions, hashtags, Instagram captions, general writing or subtitle spelling), explain what you want and what you dislike, and optionally provide a rejected and an approved example. Click **Remember this feedback**.

When editing a draft, you can also select **Remember my changes as examples for future drafts** before saving. Normal edits are not silently treated as permanent preferences. Creator metadata explicitly declared as English (`metadata_language: "en"`) stays as supplied. Other metadata sidecars receive the final English conversion pass before becoming drafts.

The local model receives saved writing guidance before producing future drafts. Publishing output always uses proper English; even a non-English reference must be expressed in English. Saved feedback refines style without changing that fixed language rule. Recent guidance takes priority over conflicting older feedback. Examples demonstrate style rather than facts: a Mumbai Indians example must not make the assistant add cricket hashtags to an unrelated cooking video. The model's generation cache includes the preference context, so changing that context changes the cache key.

Subtitle spelling memory accepts one incorrect word and one corrected word. Future Auto Captions and newly generated Shorts replace exact whole-word matches while preserving punctuation and word timings. A current supplied script has priority. Spelling changes also invalidate the publisher's cached Shorts generation. Existing rendered videos and already scheduled posts are not rewritten.

Review saved lessons and disable or re-enable any of them. Disabling removes the lesson from future generation context without deleting its history. The writing model currently receives up to 16 recent writing records, with bounded example lengths and a 6,000-character total context budget; all records remain stored locally. Do not place credentials in feedback examples.

This is persistent preference and example retrieval, plus deterministic spelling correction. It does **not** retrain Qwen's model weights, guarantee every generated draft will obey the examples, or autonomously rewrite caption animation/layout code. Timing, motion and alignment defects still need changes to the renderer. Keep reviewing facts before authorizing a new batch.

Memory is stored under `cache/creator-memory/preferences.sqlite3`. It is local to this project and survives restarts. This extra learning layer does not require loading another AI model.

### Permanent content-only publishing correction — 18 October 2026

The creator explicitly requires future titles, descriptions, Instagram captions,
tags and hashtags to describe the actual video only. Production details such as
Storylens, private-upload tests, connection checks, routing, source paths and
test-duration labels belong in internal receipts. A destination channel name is
not the subject of a video. Relevant technical/tutorial subjects and Test cricket
remain valid content; this rule does not blindly ban individual words.

This correction is saved separately in General, Cricket and Gaming creator
memory, and is included in both the initial writing prompt and the final English
copy check. The final check also receives source transcript context so it can
distinguish the subject from production notes. Prompt/context changes create new
model cache keys. This updates persistent guidance, not model weights.

Existing uploads, queue metadata and explicitly supplied English metadata remain
unchanged. The creator requested no corrections to the two completed test uploads.
Evidence is in `output/validation/publishing-content-only-memory/`.

## Detailed YouTube descriptions — 18 October 2026

The creator wants substantial, unique, search-focused YouTube descriptions rather
than generic two-line summaries. Both writing passes now request a topic-focused
opening, 1-2 main search phrases, useful source-supported detail, readable
paragraphs and 3-5 relevant hashtags. The target is 1500-3500 characters when the
source supports that much detail, including Shorts. Sparse material must not be
padded with repetition or invented facts. Instagram retains its separate caption
and size limit. Existing uploads and explicitly supplied English sidecars remain
unchanged.

The preference is saved for General, Cricket and Gaming alongside the earlier
content-only rule. This is persistent guidance and prompt adaptation, not weight
fine-tuning. Search popularity must not be invented: relevant terms may come from
the video; claims about current search volume need actual research evidence.
Length alone cannot guarantee ranking or views. Evidence is in
`output/validation/publishing-seo-memory/`.

Sources: [YouTube description guidance](https://support.google.com/youtube/answer/12948449?hl=en),
[YouTube search ranking](https://support.google.com/youtube/answer/16090438?hl=en),
and [hashtag guidance](https://support.google.com/youtube/answer/6390658?hl=en-GB).

## Laptop requirements

Uploading, folder discovery, scheduling and receipts do not require an RTX GPU. Your current laptop can run those stages.
Speech analysis, local Qwen generation, optional vision and Short rendering use the existing project engines. On an RTX 5070 Ti with 32GB RAM, run preparation as the main AI workload; the daily publishing worker can run alongside ordinary editing because it primarily transfers files and waits for platform responses.
You do not need AI image/video diffusion models merely to post a finished video.

## Validation and limits

Local tests exercise duplicate prevention, India time scheduling, shared per-clip dates, multiple batch reservations, atomic queue claims, restart recovery, changed-file checks, scope-bound authorization, missing account setup, metadata limits and Windows token encryption. Provider tests use simulated APIs; they are not proof that a specific account has been granted public publishing permission.

The complete project suite passed **307 tests** after the publishing and learning additions. The final publishing/learning/API subset passed **54 tests** after strengthening reference guidance. A local demo under `output/validation/publisher-demo/report.html` uses a real source video and an existing rendered Short, produces three draft platform posts with shared 7 PM Short dates, and confirms re-preparation creates no duplicates. No new Short was rendered in this demo.

Historical learning test, before the creator set the permanent English rule: a real local Qwen test first missed the requested writing language and description length. After supplying rejected and approved reference examples and strengthening preference guidance, it produced a two-sentence Roman Hinglish description and a caption with three hashtags. This same-source test verifies retrieval/reference imitation; it is not proof that the model will generalize perfectly. The raw outputs and checks are saved with the demo. Test preferences were added only to the isolated demo profile, not the production project.

The final English publishing revision passed **39 affected memory, provider and app API tests**. A live local Qwen check with older Hinglish references produced the English title “A Special Feeling at 7000 RPM”, an English description and an English Reel caption. The result is saved in `output/validation/publisher-demo/english-metadata.json`. A separate final translation pass covers all automatically generated publishing fields and undeclared-language metadata sidecars.

The real-account checks still to perform are: Google OAuth login, one private upload and thumbnail, channel processing verification, compliance-audited public scheduling, Meta permission setup, hosted media fetch, and one test Reel publication. No real public upload was performed during implementation.

## Official references

- [YouTube video upload and public-upload restriction](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube scheduled publishAt and video status](https://developers.google.com/youtube/v3/docs/videos)
- [YouTube custom thumbnail upload](https://developers.google.com/youtube/v3/docs/thumbnails/set)
- [Meta Instagram Login content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/)
- [Meta's official Instagram API collection and permissions](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)

## Implementation map

- `hinglish_publish/service.py`: folder discovery, preparation tasks, account-bound authorization, Shorts reuse, cloud staging and worker.
- `hinglish_publish/metadata.py`: transcript/thumbnail context and local writing.
- `hinglish_publish/store.py`: SQLite jobs and receipts, calendar allocation, atomic claims.
- `hinglish_publish/providers.py`: Google OAuth, YouTube upload/schedule/verification and Meta publishing.
- `hinglish_publish/secrets.py`: Windows DPAPI account token storage.
- `hinglish_publish/worker_lock.py`: single-worker process lock.
- `hinglish_app/static/publisher.html`, `.css`, `.js`: dashboard.
- `config.publish.local.json`: this computer's settings, ignored by source control.
- `cache/publisher`: private queue, encrypted tokens, staged thumbnail copies and reuse markers.

The core scope is a tested local publishing foundation with official account adapters. Public account approval and the first live publishing test remain prerequisites for unattended production use.
