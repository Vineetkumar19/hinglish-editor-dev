# Models and processing dependencies

Model files are installed separately from this source snapshot. Their presence on the owner's machine does not establish that they can run on another laptop.

The sanitized model-settings.json lists selectors, backends and path-related settings found in the reviewed local configuration files. Inspect the actual runtime resolver before treating an alias as the weight identity. These settings are a configuration snapshot and not an inference test.

## Role map

| Role | Source to inspect | Setup requirements |
| --- | --- | --- |
| General editing and semantic planning | hinglish_app/assistant*.py and model selectors | Configured text model, tokenizer and backend |
| Visual interpretation and image retrieval | hinglish_visuals, hinglish_broll, model selectors | Feature-specific vision and embedding model |
| Voice assistant understanding | hinglish_app/support_call_local.py | Configured Ollama model and deterministic control catalogue |
| Voice recognition and speech | hinglish_app/support_call_speech.py | Shared Cortana Whisper speech assets and selected Piper ONNX voice |
| Agent research and drafts | components/agents/core/workflow_brain.py | Configured ChatGPT/Codex route and the documented local fallback policy |
| Caption alignment | hinglish_captions | ASR and alignment dependencies for the selected path |
| Image/video generation and gaze correction | hinglish_aigen, hinglish_aiimage, hinglish_aivideo, hinglish_eyecontact | Feature-specific optional models, SDK and compute requirements |
| Finance summaries | components/finance-tracker/server/providers.mjs | Configured local model for explanations; ledger calculations remain in domain.mjs |

Paths in this table are inside components/storylens unless a full component path is shown.

## Install a model

For each required role record the upstream source, revision, license, exact filename, quantization, runtime format, file size, checksum and destination. Copy or download only the approved revision, verify its checksum, then register it with the selected backend. Custom adapters require their matching base model and configuration.

Tokenizer files, processor/configuration files and vision projectors can be required alongside the main weights. A model filename or a small adapter alone is insufficient for a complete installation.

Confirm available RAM, VRAM, disk space and platform support before selecting a configuration. CUDA, CPU offload, Apple GPU execution and voice runtimes are distinct paths. The current source's Windows behavior has not been certified on a Mac.
