# Editor integrations

**Cinematic Reels:** the Premiere and Resolve panels now open the separate
music-led assembly workspace and import its latest completed reel as a new
sequence. See [Cinematic Reels](../docs/CINEMATIC_REELS.md) for selection, retiming,
rendered shot copies and native-host validation limits.

**16 October 2026 — Beat Studio:** Premiere CEP/UXP and the Resolve Studio
window now expose **Detect & mark beats** and **Apply effects to beats** as
separate actions. Light / Medium / Strong density and a maximum marker count
control how many beats are kept. Effects currently use built-in zoom pulses on
a duplicate timeline. See [Beat Studio](../docs/BEAT_STUDIO.md) for supported
inputs, backups, pack limitations and the live-host validation boundary.

**15 October 2026:** After Effects integration, a Resolve Studio window,
Desktop/Plugin purchase editions and signed device activation are now prepared.
These are source preparation builds, not signed customer installers. See
[customer release details](../docs/CUSTOMER_RELEASE_AND_PLUGINS.md).

- `premiere-cep`: Premiere Pro 2022–2024 panel. Select clips, click Smart Clean, Script Edit, or Auto Captions, and the generated XML is imported into the project.
- `premiere-uxp`: Premiere Pro 25.6+ panel using Adobe's current UXP API, including Auto Captions and its optional spelling-reference script.
- `davinci-resolve-studio`: Resolve Studio Workspace script. It starts the local dashboard and the finished XML is imported with one button.

The editor panels use the same local bridge as `Run Hinglish Editor.bat`. Processing remains on the computer. Original sequences are not overwritten; generated XML imports as a new editable sequence.

Auto Captions offers fifteen templates. **Typography 1** recreates the supplied premium reference language with colored strips, hero-word hierarchy, shadow, glow, blur and camera motion. Its result page opens Caption Studio, where every caption can be corrected and the template, font, position, size, and aspect ratio can be changed before rebuilding the XML.
