# Storylens: new laptop setup

**Historical initial audit.** Setup has progressed since this note was written.
See [the current model/setup report](docs/LOCAL_MODELS_LAPTOP.md) for installed
software, real GPU tests, ongoing downloads and the remaining Eye Contact step.
The failures and pending items below describe the initial migration state.

Prepared on 17 October 2026 for `D:\Full Drive\remove silence`.

## What is already available

- Verified GPU: **NVIDIA GeForce RTX 5070 Ti Laptop GPU**, 12,227 MiB VRAM; driver 617.42. The GPU is working at the NVIDIA driver level. PyTorch GPU inference has not yet been tested on this laptop.
- CPU, RAM and storage supplied by you: Ryzen 9 8940HX, 16 GB RAM and 1 TB storage. Windows hardware queries for CPU/RAM were unavailable in this session.
- Chrome and Edge executables are present. The editor UI and motion renderer can use these browsers.
- Microsoft Visual C++ x64 runtime is installed (v14.50.35719.00).
- Windows Package Manager (`winget`) is present.
- Codex provides its own Python 3.12.14, Git and Node runtimes. These are usable inside this session, but they are not a normal standalone development installation on your Windows PATH.
- You confirmed that another 200 GB can be allocated to `A:` when needed. Storage is not a project constraint, and no partition change is needed for this onboarding step.

## Software checklist

| Application | Needed for | Action |
| --- | --- | --- |
| Python 64-bit, version 3.12 or 3.13 | Main editor and setup scripts | Install a supported version and create a fresh project environment. The project was developed on 3.12; its configuration and setup scripts also allow 3.13. |
| Ollama for Windows | Preferred local Qwen assistant, motion and sound planning; optional vision evaluation | Installed: version 0.40.5. Its localhost API responded successfully. Model downloads are a separate step. No cloud account is needed for these local models. |
| NVIDIA driver | CUDA inference | Already installed and responding. Verify a real CUDA computation after installing GPU PyTorch before considering a driver change. |
| Chrome or Edge | Editor dashboard and HTML motion rendering | Already present. |
| Visual C++ x64 Redistributable | Native Python/AI runtime libraries | Already present. Reinstall only if a specific DLL error requires it. |
| Visual Studio Code | Convenient source editing | Optional. [Official download](https://code.visualstudio.com/Download). |
| Git for Windows | Version control and some optional source installations | Recommended for development. Codex already has a bundled copy. [Official download](https://git-scm.com/downloads/win). |
| Premiere Pro / After Effects / DaVinci Resolve Studio | Host plugins and further timeline editing | Install the editor you use. The standalone application does not require all three. |

The main editor does not need Docker, WSL, Anaconda, a Node development server, or the full CUDA Toolkit. Core video processing uses PyAV and `imageio-ffmpeg`. Some specialist reference-analysis scripts may need separate FFmpeg/ffprobe tools.

## Downloads and installation status

Official installers are saved in the project's `downloads` folder:

- `python-3.13.16-amd64.exe`: downloaded; valid Python Software Foundation digital signature. This is the current 3.13 Windows release checked for this note. It is allowed by this project's Python version constraint; project inference on 3.13 has not been validated here.
- `python-3.12.10-amd64.exe`: downloaded; valid Python Software Foundation digital signature. This is a legacy compatibility installer, not the current security patch level. Python.org distributes later 3.12 security releases as source only. Prefer the current supported 3.13 Windows installer for a fresh standalone installation unless retaining a maintained 3.12 distribution.
- `OllamaSetup.exe`: downloaded (1,584,489,392 bytes); valid Ollama Inc. digital signature. **Installed successfully**, version **0.40.5**, at `C:\Users\Vineet Kumar\AppData\Local\Programs\Ollama`. Both `ollama --version` and `http://127.0.0.1:11434/api/version` confirmed the version. The local server is running. Model inference has not been benchmarked.

Automatic Python 3.13 installation was attempted, but Windows Installer returned `0x80070003` when opening its cached `core.msi`. Python 3.13 installation is **not confirmed**. Logs are in `downloads/python-install*.log`. The signed installer is available to run manually from Windows if this remains unresolved.

When installing Python manually, enable **Add python.exe to PATH**, then open a new terminal. The project supports Python below 3.14; do not select 3.14/3.15 for this existing dependency set.

## Important migration issues found

Installing applications is only the first part of moving this project:

1. **The copied `.venv` does not run.** Its base Python path is `C:\Users\vinee\.cache\codex-runtimes\...`, and it was created in `E:\remove silence`. Running its Python executable fails on the new laptop. Recreate the environment; copying one between computers is insufficient.
2. **The copied PyTorch packages are CPU-only.** Their version is `2.9.1+cpu`. GPU use requires replacing them with the matching CUDA packages.
3. **Model manifests still point to `E:\remove silence`.** Check `models/meaning-upgrade.json`, `models/meaning-models.json` and `tools/llama/runtime.json`. They contain absolute paths that need to be regenerated or relocated.
4. **AI generation still points to the old install.** `config.aigen.local.json` describes a GTX 1650 with 4 GB VRAM and `D:\HinglishEditorModels`. The generation environment is not included at that location in this project folder. Its presence elsewhere has not been verified.
5. **The bundled Qwen fallback is explicitly CPU-only.** `hinglish_broll/llm.py` starts the supplied llama.cpp server with `-ngl 0`. CUDA PyTorch does not change this setting. Several features prefer Ollama, while some directly use the bundled fallback.
6. **The dashboard initially offers CPU mode first.** Select **NVIDIA RTX** for tools that support it after CUDA validation. Smart Clean's VAD remains a CPU implementation.
7. **Some reference-study scripts deliberately use CPU inference** because of crashes on the old machine. Those choices need individual validation on the new GPU.
8. **Old source/library paths need checking.** Sound settings include old user-folder defaults, with a project-library fallback. Existing reports/timelines and documentary reference records can still point to original drives. Keep the saved reference memory and source videos.
9. **This folder is not currently a Git checkout.** A bundled Git executable does not restore the project's absent `.git` history.

The documentary SQLite database is present, as are Swift, faster-whisper, E5, MMS and Qwen model-cache directories. Some caches contain `.incomplete` download files; a directory's presence does not prove its selected weights are complete. Check the actual snapshot files and load them before redownloading or deleting anything.

## Core editor setup order

1. Complete Python installation using `downloads/python-3.13.16-amd64.exe`. Ollama installation is already complete. Windows Installer's automatic cache-path failure may require running the Python installer yourself from Windows.
2. In File Explorer, rename the existing `.venv` folder to `.venv-old-laptop` to keep a backup (choose another backup name if that one already exists). The next setup step will create a clean `.venv`. If using Python 3.13, install packages afresh; do not reuse Python 3.12 binary packages.
3. Run **Setup RTX 5070.bat**. Its GPU configuration also targets this 5070 Ti. It installs matched `torch==2.9.1` and `torchaudio==2.9.1` CUDA 12.8 packages, then the project requirements and dependency doctor.
4. Repair/regenerate local model manifests. Check existing cached weights before downloading them again. **Download Phase 2 Models.bat** is the existing preparation entry point, but setup and paths need validation first.
5. Open a new terminal and download the preferred local planning model:

   ```powershell
   ollama pull qwen3:8b
   ```

6. For the optional Smart Visuals vision evaluator:

   ```powershell
   ollama pull qwen2.5vl:7b
   ```

7. For the Sound Design Ollama vector index, if using that feature:

   ```powershell
   ollama pull qwen3-embedding:0.6b
   ```

8. Run **Run Hinglish Editor.bat**, select **NVIDIA RTX**, and verify a short real clip before processing a large batch. CUDA arithmetic, real speech inference and editor import still need validation on this laptop.

The saved documentary memory uses the **separate Hugging Face E5 embedding model** `intfloat/multilingual-e5-small`. Keep that encoder with its existing index; the Ollama sound embedding model does not replace it.

## Optional features: install when needed

- **AI Images:** `Setup AI Images (RTX).bat` creates a separate generation environment and downloads Z-Image Turbo. The project estimates about 21 GB of image weights.
- **AI Video:** `Setup AI Video (RTX).bat` adds Wan 2.2 TI2V 5B. The project estimates about 24 GB of video weights. Both features share the generation environment; package installations and temporary files use additional disk space.
- **Eye Contact:** its setup additionally needs Git, Git LFS, CMake, Visual Studio C++ Build Tools and the NVIDIA Maxine AR SDK. NVIDIA access/credentials may require your participation. This toolchain is not required for ordinary editing.
- **Subscription website:** install `requirements-saas.txt` and MySQL if operating the MySQL account service. MySQL is separate from the standalone editing engines.
- **Publishing:** install `requirements-publish.txt` or use `Setup Publishing.bat` when setting up your publishing accounts.

## Performance priorities for this laptop

First establish a working CUDA environment and a real short-clip baseline. The current software configuration prevents the project from taking advantage of the GPU, so a speed estimate now would be unreliable.

The generator automatically chooses **CPU offload** for an 11–22 GB GPU. Your 12 GB card falls into this range; the project does not expect these diffusion pipelines to remain fully on the GPU. With your current 16 GB system RAM, memory pressure during offload may be substantial. A later 48 GB upgrade provides more room, but actual generation speed and stability still need measurement.

Start with the existing Qwen 8B planning path and one heavy task at a time. The application has a shared editing lane, but separately launched Ollama jobs, reference workers and desktop editors can still compete for memory. Close large unused applications during the first benchmarks. Large-model downloads have not been started automatically in this onboarding pass.

## Official references checked

- [Python Windows releases](https://www.python.org/downloads/windows/)
- [Python 3.12.15: source-only security releases](https://www.python.org/downloads/release/python-31215/)
- [Ollama Windows download](https://ollama.com/download/windows)
- [Ollama Windows installation and model storage](https://docs.ollama.com/windows)
- [Official PyTorch 2.9.1 CUDA installation commands](https://pytorch.org/get-started/previous-versions/)
- [Microsoft Visual C++ runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
