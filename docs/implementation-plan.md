# Implementation plan

1. Define immutable transcript/media/selection records and validated JSON settings.
2. Write behavioral tests for matching, cuts, evaluator, CTC and XML export, then implement the pure Python core.
3. Add PyAV media inspection, strict CFR checks and disk audio extraction/assembly.
4. Add local Hinglish ASR, Silero VAD and romanized multilingual CTC adapters with explicit failure states and lazy imports.
5. Orchestrate cached analysis, selection, cut evaluation, bounded retry, HTML/JSON reporting and XML export. Provide a no-model synthetic demo and diagnostic command.
6. Add Windows setup/run launchers, input folders, configuration and instructions. Verify the core, CLI demo, audio reconstruction and XML consistency. Record untested model/editor integration limits.
