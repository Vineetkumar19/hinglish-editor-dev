# Storylens Template Assembler

An ordered AEP composition assembler for After Effects and Premiere Pro.

1. Open **Window > Extensions > Storylens Template Assembler** in AE, or
   **Window > Extensions (Legacy) > Storylens Template Assembler** in Premiere.
   Restart the relevant editor after saving your work if the new entry is absent.
2. **Add projects** or **Browse library**, select the AEP files, then **Read compositions**.
   The default library is `D:\Editing\AE documentry style editing templates`.
3. Check each composition choice. Recognizable Main / Render / Final names are
   suggested; ambiguous and nonstandard names require a manual selection.
4. Set the displayed order with the arrows. Set a target such as **10:00**.
5. **Build new composition / Build new Premiere sequence**. The last item trims
   to the target on an output frame. Animation speed is unchanged.

The default uses the full composition. Work-area-only assembly is optional.
If the list is too short, building stops with an explanation. **Repeat in order**
is opt-in; it reuses the same source comps. Edits to a repeated source comp affect
its other occurrences. Extra selected templates after the target are unused.
AE builds a separate composition and uses quarter-resolution preview to reduce RAM.
Sources, existing timelines and the owner's project file are not overwritten or
automatically saved. Save the Adobe project yourself when ready.

## One editor at a time

Read the selected projects once in After Effects. Their actual composition names,
dimensions, durations and source timestamps are cached under
`Documents\Storylens\template-assemblies`. You can then close AE, open Premiere,
add the same projects (or load your saved ordered list), and **Read compositions**
from the cache. Source changes require another AE inspection. The panel never
starts the AE interface automatically from Premiere. Dynamic Link itself uses
Adobe background processes and still consumes memory.

Premiere imports the selected original AEP compositions using Dynamic Link,
then assembles them into a new sequence. Edit the linked compositions in AE;
they do not become native Premiere text/effect layers. AE and Premiere need
compatible versions. Duplicate composition names within one AEP cannot be
disambiguated by Premiere's name-based import API: rename in a source copy or
choose a unique composition. Fonts, plugins, linked footage and existing template
expression errors remain the source project's responsibility.

## Installation and standalone AE panel

The owner approved enabling unsigned CEP panels and per-user installation on
25 October 2026. `Install.ps1` installs under the user's Adobe CEP extensions,
backing up an earlier installed copy. `-EnableUnsignedPanels` sets the per-user
CSXS 11/12 debug flags; this permits other unsigned CEP extensions too. It is
never changed without that explicit option. Existing Storylens plugins are kept.

Without CEP, use **File > Scripts > Run Script File** and choose
`Template Assembler.jsx` in this folder. This resizable ScriptUI panel runs in AE
and uses the same native engine. Keep the adjacent `host.jsx` and `model.js`.

## Validation status

Actual AE 2026 validation used Historical_Documentary_v6.aep (Slideshow, 32 s,
24 fps) and The Fog of History Logo.aep (Main, 14.04 s, 25 fps). With Repeat in
order enabled, the panel created 27 native placements, exactly 600 seconds /
14,400 frames at 24 fps. Every native placement boundary was checked for gaps
and overlap; the last placement runs from 598 to 600 seconds. Mixed-size fitting
uses 100% and 200% scale for these 4K/1080p sources. The source project path stayed
`D:\AE mere edited files\1.aep`; no project save was issued.

Evidence: `output/template-assembler-evidence`. Six focused planner checks and
JS syntax checks pass. A source-template missing-font notice was acknowledged;
the owner's existing expression-error banner remains. This is timeline assembly
validation, not a render-quality or every-template compatibility claim.

The dockable CEP menu needs the editor's normal restart to discover the newly
installed extension. Its loaded-panel validation and Premiere's Dynamic Link
workflow remain pending; Premiere was closed to honor the one-editor/RAM request.
Do not describe those paths as end-to-end verified.

## API references

- https://ae-scripting.docsforadobe.dev/general/project/
- https://ppro-scripting.docsforadobe.dev/general/project/#projectimportaecomps
- https://ppro-scripting.docsforadobe.dev/general/project/#projectcreatenewsequencefromclips
- https://ppro-scripting.docsforadobe.dev/item/projectitem/#projectitemsetscaletoframesize

No rendering, local model call or internet upload is required to assemble templates.
