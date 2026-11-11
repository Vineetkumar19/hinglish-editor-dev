# Cortana model and runtime strategy

Review date: 20 October 2026. These are evidence-backed candidates and a proposed test order, not benchmark winners on this laptop. No candidate weights were installed or executed during this review.

## Owner-selected vision model — 22 October 2026

The owner requested Qwen-VL 8B Q4 for vision. The selected official Ollama
artifact is `qwen3-vl:8b-instruct-q4_K_M` (Qwen3-VL 8B Instruct, Q4_K_M language
weights with its matching vision projector). Official tag details:
[Ollama model](https://ollama.com/library/qwen3-vl:8b-instruct-q4_K_M).
Ordinary conversation continues to use `cortana-local:9b` (Qwen3.5-9B Q6_K).

Image-bearing chat/tool rounds, visual recipient extraction and the explicit
screenshot analyzer use `ollama_vision_model`. Text-only turns use `ollama_model`.
The model name is shown in screen replies and in Settings under Vision model.
Images remain local; changing models does not authorize any cloud fallback.
Installation and actual screen acceptance are recorded in LIVE_ACCEPTANCE_CHECKLIST.md.
The older candidate map below is historical, not the current vision selection.

## Selection rule

Choose the smallest model that passes the real Cortana workflow suite with acceptable latency, language accuracy and memory use. Keep distinct roles, but share a model when it is good enough across roles. A Finance or Career specialist does not need its own large resident model. Deterministic tools, exact source retrieval and verification matter more than naming a separate LLM for every agent.

Record model ID and immutable revision/digest, format/quantization, license/access status, inference engine, capabilities, supported language tests, peak RAM/VRAM, warm/cold latency, quality and failure modes. Pin the proven choice; a mutable `latest` tag is not a deployment manifest.

## Initial candidate map

| Role | Proposed starting point | Alternatives and gate |
| --- | --- | --- |
| Core planning, tool selection, Hindi/Hinglish conversation | Qwen3.5-9B, quantized local Ollama artifact | Compare Qwen3.5-4B for fast routine commands. Begin in non-thinking mode with a bounded context. Validate tool schema fidelity and mixed-language requests, not only fluent chat. |
| Screen understanding and document vision | Reuse Qwen3.5-9B on demand | First read accessibility/DOM/OCR structure. Compare 4B for latency; add a separate vision model only if measured failures justify it. |
| Developer reasoning and code patches | Qwen3.5-9B with source/test tools | Qwen2.5-Coder-14B-Instruct is an optional comparison for bounded code generation, not a promised upgrade or a second always-loaded agent. Its coding performance and agent/tool protocol must be tested separately. |
| Fast multilingual speech input | Faster-whisper with multilingual large-v3-turbo | Existing integration makes this the recovery baseline. Compare Qwen3-ASR-1.7B on the user's English/Hindi/Hinglish clips. Use 0.6B only if latency/memory wins while quality passes. |
| Offline Reel transcription/captions | Faster-whisper large-v3 versus turbo | Choose from actual mixed-language caption errors and word timing. Editorial alignment is a distinct test from transcription quality. |
| Natural Hindi/English/Hinglish speech output | Audition Indic-Speak with a consistent authorized stock voice | It explicitly targets mixed Indic/English speech, but access is gated and license terms require user review. Compare smaller Indic Parler-TTS for footprint and native Windows synthesis as a recovery fallback. Neither is a quality winner until heard on this machine. |
| Wake phrase | Custom evaluated 'Hey Cortana' detector using openWakeWord/ONNX on CPU | Start with push-to-talk until a custom detector passes real accent/noise tests. Included pretrained models are not automatically a Cortana detector. |
| Voice activity detection | CPU Silero VAD integration | Tune pauses/noise and end-of-turn behavior on the user's speech. |
| Knowledge embeddings | Qwen3-Embedding-0.6B | Use CPU or short queued batches; combine with lexical/structured search. Compare retrieval quality before adding a larger embedding model. |
| Optional reranking | Qwen3-Reranker-0.6B | Add only when measured retrieval failures justify the latency and memory. |
| Finance calculations and matching rules | Deterministic code, decimal arithmetic and dated data | LLM writes explanations and suggests classifications; it does not invent prices, totals, resume evidence or certainty. |
| Video editing/rendering | FFmpeg/ffprobe, structured edit decisions and parameterized assets | Use GPU encoding only after the installed build, chosen codec/filter path and output quality are verified. No per-frame LLM editing. |
| Difficult cloud reasoning | User-approved provider/model selected at the time of use | No automatic fallback. Approval binds provider, data categories, purpose and budget. A cloud answer never bypasses local tool authorization. |

## What the primary sources establish

- **Qwen3.5-9B:** the publisher documents language/image capability, tool-use examples and configurable non-thinking behavior. Ollama lists a llama.cpp Q4_K_M variant with about 5.6 GB language weights plus a 922 MB projector (about 6.6 GB combined on the page); other artifacts differ. Runtime memory also includes cache, buffers and engine overhead. This makes it a candidate for 12 GB VRAM, not a guarantee at arbitrary context length. Sources: [publisher model card](https://huggingface.co/Qwen/Qwen3.5-9B), [Ollama artifact details](https://ollama.com/library/qwen3.5:9b).
- **ASR:** Qwen3-ASR lists English and Hindi and provides streaming/offline interfaces. Its separate forced aligner lists 11 languages and does not list Hindi. Do not assume that timestamp support makes it a validated Hindi/Hinglish caption aligner. Source: [official Qwen3-ASR card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B).
- **Existing ASR runtime:** faster-whisper documents GPU execution, word timestamps, VAD and turbo loading. Its current GPU instructions call for CUDA 12 cuBLAS and cuDNN 9. Verify the actual CTranslate2 build and Blackwell GPU path with a smoke transcription; a GPU driver alone is insufficient. Source: [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **TTS:** Indic-Speak's card explicitly discusses code-mixed Indic/English speech and stock speakers shared across Hindi and English. The card is gated, uses a custom Indic Open Model License and a roughly 3.8B-parameter speech LM. The page's example checkpoint differs from its repository name: verify the exact downloadable revision and inference code before adopting it. Do not assume it fits concurrently with the main model or reproduces advertised latency here. Source: [Indic-Speak card](https://huggingface.co/bodhan-ai/indic-speak). Review the [full model license](https://github.com/Bodhan-AI/bodhan-model-info/blob/main/licenses/indic-open-model-license/v1/Indic_Open_Model_License.md) and upstream terms before acquiring or distributing weights; no acceptance was performed in this review.
- **Smaller TTS comparison:** Indic Parler-TTS supports Hindi and English and has a smaller 0.9B model. Mixed-language pronunciation still needs direct testing. Its card also has an access gate. Source: [AI4Bharat card](https://huggingface.co/ai4bharat/indic-parler-tts).
- **Wake:** openWakeWord has an ONNX path on Windows; its current stated language support is English. Code is Apache 2.0, while included pretrained weights have CC BY-NC-SA terms. Evaluate a custom English wake phrase spoken with the user's accent; this does not provide multilingual speech understanding by itself. Source: [upstream project](https://github.com/dscripka/openWakeWord).
- **Retrieval:** Qwen3-Embedding-0.6B is a small multilingual embedding model; use its instructed-query convention and preserve exact source passages alongside vectors. Source: [official model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
- **Coding comparison:** Qwen2.5-Coder-14B-Instruct is a code-focused model. It is a comparison candidate, not evidence that it beats the newer general/vision model on this user's Java/React tasks. Source: [official model card](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct).
- **Rendering:** FFmpeg provides the deterministic filter primitives needed for silence detection, trimming, captions, LUTs, loudness and black-frame checks. Templates and verification remain Cortana code. Source: [official filter documentation](https://ffmpeg.org/ffmpeg-filters.html).

## Resource plan

The laptop has 12 GB VRAM but only 16 GB installed system RAM. At inspection an unrelated StoryLens model occupied about 10 GB VRAM. Do not treat free GPU capacity as static and do not automatically stop another project's model.

Use a scheduler that tracks owned worker memory, task priority, queue state and cancellation. Start with one heavy worker at a time. A realistic stage order is VAD/wake on CPU -> ASR -> main reasoning/tools -> TTS, with owned models unloaded or kept warm only as measurements allow. Media transcription/rendering receives its own resource phase. Batch content work must yield or pause when interactive voice needs resources.

A model file's size is not its peak memory footprint. Measure model load peaks, context-cache growth, vision input resolution, TTS generation and subprocess memory. A fallback policy is to reduce a supported context/image size, use the validated small model, or queue; never silently invoke a cloud service. Keep headroom for the display, IDE and browser.

Do not adopt a second heavy coder, large embedding model, continuous vision loop, always-on speech LM and full local agent stack simultaneously. Larger MoE models still require storage and resident weights even when only a subset is active per token.

## Benchmark before final selection

1. Establish compatibility in isolated, pinned workers. Proposed base Python is 3.12; newer speech/ML packages may use a separate worker environment rather than destabilizing FastAPI.
2. Record load time, peak RAM/VRAM and whether all intended model layers actually run on GPU.
3. Test the same 90-command language set, short replies, correction turns, real app names, source-code identifiers, addresses, dates and amounts.
4. Score task completion and valid tool arguments; fluent explanations do not count as successful actions.
5. Test screenshots of actual IDE errors and ordinary apps, with exact UI/source verification.
6. Compare code candidates on identical small Java/Spring Boot and React bugs with tests. Do not let either see hidden expected patches.
7. Compare turbo/large-v3/Qwen ASR on recorded clean/noisy/mixed-language samples. For captioning inspect boundaries separately; Hindi forced alignment is an unresolved gate for Qwen's aligner.
8. Listen to TTS names, technical terms, Roman Hindi, Devanagari, dates/numbers and mixed sentences. Measure time-to-first-audio and interruption; choose a female stock voice with the user's input, not an unlicensed character imitation.
9. Test model handoff while StoryLens/IDE/browser are in use. Record contention rather than evicting them.
10. Promote only a candidate whose supported workflow suite passes. Leave alternate workers optional.

## Building tools versus runtime tools

Claude Max can help implement and review Cortana during the build month. Current Anthropic documentation describes claimable API credits on eligible Max plans, with billing-cycle expiry and separate API limits. Eligibility and balance are account-specific and have not been checked here. Source: [official Max API credit documentation](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers).

Keep this distinction explicit: the subscription may fund build assistance or approved API use, but the local runtime, saved workflows and ordinary voice/task execution must remain useful when that subscription ends. Do not reuse browser-session credentials as a substitute for a supported API integration.

## Research limits

Model cards and upstream documentation were checked, but no universal 'best model' can be established without this laptop's task/voice tests. Publisher benchmark scores and latency claims are not measurements here. No gated terms were accepted, no cloud inference was performed, no model was downloaded, and no account credentials were inspected or used.
