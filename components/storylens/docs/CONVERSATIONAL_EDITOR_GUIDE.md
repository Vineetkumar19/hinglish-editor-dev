# Conversational video editing

Open **Run Hinglish Editor.bat**. The editing assistant appears on the right. Add your clips using **Attach** or drag them into the chat, describe the edit, and press **Send**. The assistant selects the tools, opens the relevant editing view and runs the existing engines. You can close the assistant or press **Show tools** to reveal the dedicated controls.

## Everyday requests

- “Clean these ten clips and combine them into one video.” Smart Clean processes the takes, then the assistant joins the cleaned videos in attachment order.
- “Arrange these takes using my script.” Attach a `.txt` outline/script with your videos. Script Edit finds the matching spoken parts. If the script is missing, the assistant asks for it.
- “Add captions using Typography 4.” The assistant selects that exact caption template. All five custom typography styles and the other existing templates are available.
- “Make 10 Shorts from this long video, with Typography 5 captions.” The Shorts engine receives the requested count and caption settings. The number of suitable clips still depends on the source footage.
- “Clean this, then add captions.” The assistant runs the steps in order. The next tool receives the edited video, not the original recording.
- “Add smooth, subtle zooms.” Smart Zoom opens and processes the video.
- “Design cinematic sound for this video.” Sound Design adds its music/effects workflow.
- “Add B-roll”, “Add smart visuals”, “Correct eye contact”, “Generate AI images”, “Generate AI video” or “Make motion graphics.” Each request connects to the corresponding existing tool. Script-only generation is supported by AI Images, AI Video and Motion Graphics when an explicit narration script is provided.
- “Upload this on YouTube.” A finished MP4 can be attached or reused from the last edit. The chat prepares publishing drafts with English titles, descriptions, captions and tags. Publishing Studio opens for account, audience, disclosure and schedule review and final authorization. The chat does not silently authorize public posting.

After a completed edit, simply say “Now add captions” or “Now add zooms.” The same conversation remembers the last completed videos. Attaching new videos selects those instead. Uploaded chat media remains available for follow-up work; original files are preserved.

## Speaking instead of typing

Press **Speak**, allow microphone access in your browser, say your request, then press **Finish speaking**. The request is transcribed locally with the installed multilingual faster-whisper model and follows the same planning and editing path as a typed message. **Escape** cancels an unfinished recording. Requests are capped at two minutes and recordings at 25 MB.

Chrome/Edge or another browser that supports microphone capture and MediaRecorder is required. Voice transcription uses the downloaded Phase 2 multilingual speech model in CPU mode. It does not use the browser's cloud speech recognition service. If recording or the local speech model is unavailable, the interface explains the problem and typing remains available.

## Progress, results and recovery

The chat shows the requested steps, the current tool's activity and results. The editing panel displays its existing quality report and editable XML output. The assistant renders supported output timelines into whole MP4 videos so the next step can process them, while keeping the original editable results. These renders use the sequence's canvas dimensions; renders with this shared renderer have mono audio.

**Stop after this step** allows the current operation to finish and preserves its output, then skips the remaining steps. It does not forcibly terminate a render/model halfway through writing files. Tools whose quality checks fail pause the chain for review. Missing GPU/model requirements are reported before a chain is launched. RTX-only tools are not presented as successfully generated on an unsupported laptop.

Editing requests and local planning run in one shared editing lane. This avoids overlapping large editing/model tasks started by the main editor and assistant. A separately launched publishing worker, third-party editing application or separate command-line engine is outside this lane.

Conversations and attachments are stored in `cache/assistant`. MP4s created for the chat are in `output/assistant`. Reloading the page restores conversation history and results. Restarting the server marks unfinished chat requests as interrupted; it does not silently relaunch them. Start a new request to continue from saved completed output. **New chat** starts a fresh conversation while keeping previous output files.

## Model and boundaries

Clear single-tool commands have immediate bounded routing, such as Typography selection or a numbered Shorts request. More nuanced requests and ordinary editor questions use the existing local Qwen brain. Common help questions take a separate answer-only path and cannot return executable editing steps, even if the model includes them. The model is: Ollama `qwen3:8b` when available, with the bundled local Qwen/llama.cpp fallback. This is a ChatGPT-style interface powered by this project's local models, not a connection to the ChatGPT service.

The language model can choose only the 13 supported tool destinations and validated editing settings. It cannot introduce shell commands, arbitrary executable code or file paths. Paths come from the user's explicit attachments/selection and verified editor outputs. Unknown tools/settings are rejected. Ambiguous requests receive a clarification, and essential missing files/scripts are requested in chat.

The assistant is an entry point to the existing tools. It does not reproduce every advanced review-page control as a chat command or invent new editing capabilities. Use **Show tools** or the generated review pages for detailed per-cut corrections, alternative asset selection and advanced settings. Standard generated publishing text remains English; caption language follows the existing caption engine and spoken source.

## Verified demo

A live browser test attached two three-second excerpts from the supplied `as.mp4` video and sent:

> Clean these clips and combine them into one video. Then add captions using Typography 4.

The real local Qwen planner selected Smart Clean and Auto Captions, enabled combining, and selected `typography_4`. Both tools ran without manual tool selection, the cleaned parts were joined, and the caption step received the joined video. Both tool quality reports passed. The resulting MP4 and a screenshot of the completed chat are saved under `output/validation/assistant-demo`.

The final affected test group passed **64 tests**, and **17 publishing queue tests** also passed. The Windows DPAPI encryption test was outside this affected scope. Local automated tests cover exact typography selection, Shorts count/caption routing, local model context, unknown tool/settings rejection, script clarification, continued attachment requests, output chaining, stop behavior, failed quality checks, missing RTX setup, session recovery, publishing draft preparation, HTTP authentication, file boundaries and media range streaming. Voice dispatch is tested with controlled transcription, and the real offline speech model was exercised on recorded speech from a supplied video. Physical microphone capture was not tested on the user's device. Public uploads and RTX diffusion/eye-contact generation were not performed as part of this chat feature test.

## Implementation map

| File | Responsibility |
| --- | --- |
| `hinglish_app/assistant_plan.py` | Local model planning, immediate command routing, supported tool/settings schema and job payloads |
| `hinglish_app/assistant.py` | Persistent conversations, attachments, background requests, chained editing and publishing draft preparation |
| `hinglish_app/assistant_media.py` | Timeline MP4 rendering, ordered joining and offline voice transcription |
| `hinglish_app/server.py` | Protected chat/upload/status/media routes and the shared editing lane |
| `hinglish_app/static/assistant.js` | Chat messages, drag-and-drop, microphone recording, progress, navigation and video previews |
| `hinglish_app/static/assistant.css` | Right-side panel, responsive layout and simplified conversation mode |
| `hinglish_app/static/app.js` | Reveals the selected tool/settings and watches its existing editing job |
| `hinglish_publish/service.py` | Reuses the same publishing draft preparation for folder files and explicit chat attachments |
| `tests/test_assistant.py`, `tests/test_assistant_http.py` | Behavioral and local HTTP tests |
