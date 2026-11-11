# Setup and platform compatibility

## Source review on either laptop

Clone this private repository after access is granted. Open the folder in a code editor. Read README.md and docs/FEATURES.md. No model download is required to inspect source or documentation.

## StoryLens engine on Windows

The original project expects Windows-installed editors and several D: paths. Set the reviewed installation paths before using a copied source tree. The components/ layout is for a coordinated review snapshot; existing launchers still retain their source project's path assumptions.

Inside components/storylens, create a fresh Python environment. The project metadata supports Python 3.10 through 3.13.

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python -m pip install -e .

Select a matching Torch and torchaudio build separately as the requirements file instructs. Use a supported NVIDIA driver and the appropriate CUDA wheels for GPU features. Some features have extra requirements files and setup scripts.

After dependencies, paths, required models and activation are configured, use the review startup mode.

    .venv\Scripts\python -m hinglish_app --desktop --root .

The desktop wrapper uses .NET 10 for Windows and WebView2. Its source is under desktop. A Windows installer definition exists under editor_plugins/release. Those sources do not establish that a clean end-to-end installer has passed acceptance.

## Connected projects

- Agent Suite has its own Python requirements, setup scripts and Dockerfile. Integrated StoryLens entry is scripts/storylens_server.py. Review its command arguments before startup.
- Finance Tracker requires Node 24 or later. In its component folder run npm ci, npm run build, and npm start. Its separately labelled demo uses npm run demo.
- Pocket Tracker Android needs the Gradle wrapper, Android SDK and an authorized phone. Its laptop companion starts with node laptop/server.cjs. A new laptop needs its own pairing.
- Cortana has separate Python and desktop dependencies under agent and desktop. StoryLens currently expects the shared runtime under D:/Cortana. Configure the reviewed paths and install the required speech models first.
- Cricket Desk and Gaming Desk retain their local service launchers. Read their component README or control guides before enabling research.

## Mac review

All source files can be reviewed on a Mac. A complete native Mac execution of this snapshot has not been validated. The Windows Forms desktop wrapper and Windows application control need a Mac implementation. CUDA-specific processors need compatible Mac processing routes and tests. Native editor integrations need their matching Mac installation and path handling.

A configured Windows GPU machine can host the functional review while the managers inspect source locally.

## Docker scope

Agent Suite and the SaaS backend include Docker files. They cover those services. Desktop editors, Windows UI control, GPU compatibility and phone pairing have additional host requirements. Read the configuration of each container before startup.

## Account setup

Use fresh review credentials and connections. The source package omits production browser profiles, OAuth grants, private ledgers and active queue databases. Existing configuration examples explain the expected fields. Do not copy a live cache or production environment file into this review tree.
