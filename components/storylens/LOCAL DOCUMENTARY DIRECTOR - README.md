# Local documentary director test

This is an offline Dale Steyn demonstration using the installed Ollama `qwen3:8b` model and the saved cricAddict and vineet documentry edit styles. It does not call a cloud model at runtime.

The local model chooses existing effects, scene order, durations, short English copy, photo order and sound cues. The Python adapter binds these choices to previously approved animation code. It does not create new motion, layouts or camera paths. Some original template decorations and Dale Steyn typography remain built into those templates.

The runner checks the plan and asks the same local model to correct invalid fields. A focused correction uses the model's own reasoning mode. A plan that remains invalid stops instead of deleting scenes and stretching the remaining scenes to fill the minute.

To run the demonstration yourself:

1. Open Ollama. Keep the installed `qwen3:8b` model available.
2. Open a terminal in `E:\remove silence`.
3. Run `.venv\Scripts\python.exe tools\run_local_documentary_best.py`.
4. Open `output\reference-analysis\local-documentary-best\report.html` after completion.

The process stops after 30 minutes. Re-running replaces the output in this demonstration folder, so copy a result elsewhere first if you want to preserve it.

Required existing local dependencies include the project Python environment, Ollama, Microsoft Edge, the saved style profiles, the supplied reference video on A:, the previously prepared photos/cutout/footage frames, and the local sound-effects library. No ChatGPT subscription is needed to execute this runner once those files and dependencies are available.

This is a specific local demonstration, not a finished general-purpose editor for arbitrary videos. Its source, assets and duration are currently the Dale Steyn reference and a 60-second output. Original reference narration/background audio is retained; this does not generate new narration, music or diffusion video.

The output folder records model requests and responses, locally generated correction values, animation-source hashes, the compiled plan, an encoded-frame review, audio choices and runtime. Saved style memory is instructions/examples, not fine-tuned model weights.
