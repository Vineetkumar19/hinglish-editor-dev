---
name: gaming-highlights
description: Edit a completed gaming livestream into a comedy-led 10–15 minute highlight with a 30-second opener, publish it Public on gaming YouTube with one fixed package, then schedule five YouTube Shorts starting the same IST day. No Instagram or Topaz.
---

# Gaming Highlights

Use `$gaming-highlights` for the owner's gaming replay edits, separate from Gaming OBS. Use the StoryLens workflow and the executor routes in [references/workflow.md](references/workflow.md). GPT makes editorial, visual and writing decisions. Prefer authorized OpenAI speech tools. Record and disclose the actual local speech fallback only if the needed cloud capability is unavailable. Keep the original Hindi/Hinglish audio.

## Source and job

- Reuse the exact job and completed download when available. Verify source video ID, channel, completion, duration, actual dimensions/frame rate/audio and full SHA256. When discovery is needed, use a read-only discovery agent if available. Select the latest eligible completed replay from **Vineet Kumar / @vineet_91 / UCtc3vpF9QPHAM7lTYCCulyg**. Skip live/upcoming, unrelated, and already processed sources.
- Use StoryLens Downloader **Highest available** for new downloads. Keep the largest available resolution and then the highest frame rate at that resolution. If expected quality is still processing, report it or wait. Preserve the supplied original.
- Store work and receipts under the existing `D:/Gaming/Gaming Higlights/<source-id>` folder. Record exact input, rendered output, and remote IDs/hashes. Inspect saved state before retrying. Avoid duplicate uploads, downloads, or schedules.

## Comedy-first edit

1. Review the full replay in timestamped windows. Look for the owner's **spoken Hindi/Hinglish sarcasm, jokes, playful rants, banter and reactions first**. Preserve each setup, timing, delivery and payoff. Keep original harsh or abusive wording when the delivery and surrounding exchange establish it as part of a joke. Judge the context and tone from the audio and footage. A word alone does not establish sarcasm. Gameplay is secondary and gives jokes their context. Include strong gameplay only when it adds to the edit. Skip dead time, repeats, menus, and filler.
2. Make one 10–15 minute master **including** the 30-second cold open. Use the existing StoryLens gaming renderer with a GPT-authored cut plan, editable timeline, original commentary/game stereo mix, full frame, source resolution/frame rate and NVIDIA NVENC. Skip Topaz and whole-stream Smart Clean. If the good material falls short, report the shortfall without padding.
3. Use **Intro Create → Gaming YouTube** for the 30-second opener. Use the approved World War Z: Aftermath Sarcastic Cut as a pacing reference. Pick 6–10 distinct cuts of 3–5 seconds from the highlight material. Keep the jokes intelligible and use one riser under the last cut. Align its resolving beat with the first frame of the body at 00:30. Verify the master’s actual playback, scene boundaries, picture, audio and exact format. Preserve the source-to-master cut map.

## One fixed package and Public YouTube release

- Reuse an existing owner-approved or source-matched thumbnail if supplied, including a verified thumbnail made in another chat. Save its exact path and hash with **one** factual English title, full description, tags and at least ten relevant hashtags within platform limits. Accurately describe the commentary-led edit. Keep harsh language in the original footage when warranted by the joke. Package the video accurately for a general gaming audience.
- Publish the verified highlight immediately as a **Public YouTube upload** on the exact gaming channel. Category Gaming. Select **No, it’s not made for kids** for the owner’s ordinary gaming commentary. Verify the exact remote ID, Public state, metadata, attached thumbnail and processing. Verify matching playback quality when YouTube offers it. The thumbnail and metadata stay fixed. There is no packaging rotation.
- Extract exactly five distinct, self-contained Shorts from the finished master with StoryLens **Long to Shorts**. Use the master’s own clock and checked speech timings. Prioritize complete funny moments. Verify framing, intelligible audio, source mapping, and a factual English title, description, and relevant hashtags for each.
- Schedule the five Shorts on the same gaming YouTube channel, one per day. **Start on the current IST calendar day**, as soon as the first verified Short can be released. Use the first available reasonable slot today even after the normal evening window. Subsequent Shorts use a persisted time within **17:00–20:00 IST** on consecutive days. Prior releases or schedules from other videos do not defer this batch. If local midnight has actually passed before scheduling is possible, report the missed date and use the next possible release, never backdate. Verify the five remote IDs and scheduled times or Public states.
- This workflow has no Instagram publishing, Reels, Stories, Highlights, or Instagram schedule. Finish after the exact long-form and five YouTube destinations are verified. Do not add a repeating campaign.

The owner’s specific scope can override the defaults above. Saving a skill is separate from running a job. Use the actual video and platform evidence before reporting completion.
