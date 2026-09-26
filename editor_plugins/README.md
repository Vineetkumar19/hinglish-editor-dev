# Editor integrations

- `premiere-cep`: Premiere Pro 2022–2024 panel. Select clips, click Smart Clean, Script Edit, or Auto Captions, and the generated XML is imported into the project.
- `premiere-uxp`: Premiere Pro 25.6+ panel using Adobe's current UXP API, including Auto Captions and its optional spelling-reference script.
- `davinci-resolve-studio`: Resolve Studio Workspace script. It starts the local dashboard and the finished XML is imported with one button.

The editor panels use the same local bridge as `Run Hinglish Editor.bat`. Processing remains on the computer. Original sequences are not overwritten; generated XML imports as a new editable sequence.

Auto Captions offers fifteen templates. **Typography 1** recreates the supplied premium reference language with colored strips, hero-word hierarchy, shadow, glow, blur and camera motion. Its result page opens Caption Studio, where every caption can be corrected and the template, font, position, size, and aspect ratio can be changed before rebuilding the XML.

Timeline features (B-roll, Smart Visuals, Smart Zoom, Sound Design, Eye Contact) work on the sequence open in Premiere, or on the timeline open in Resolve, and import a new sequence. **Smart Visuals** adds real logos, faces, places and archival footage of what you talk about, fetched from Wikipedia/Wikimedia Commons, with pop-ups on V3 and full-screen visuals on V2.
