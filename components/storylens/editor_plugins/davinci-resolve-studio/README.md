# Hinglish Editor for DaVinci Resolve Studio

**15 October update:** the script now opens a native UIManager window with
twelve tool choices, progress, review and import controls. Resolve Studio and
its Python scripting support are required. This laptop has no Resolve install,
so in-host testing is still pending. See the customer release guide in
`docs/CUSTOMER_RELEASE_AND_PLUGINS.md`; this source is not a signed commercial installer.

This integration uses the same local dashboard and Python engine as Premiere.

1. Run `Install Editor Plugins.bat` once.
2. In Resolve Studio choose **Workspace > Scripts > Hinglish Editor**.
3. Choose Smart Clean or Script Edit and create the timeline.
4. Click **Import to Resolve**. The new editable timeline appears in the open project.

Resolve Free, old versions, and modified versions can use the same dashboard and import the generated XML manually. A commercial Store build can wrap this local interface as a signed Workflow Integration; the editing engine and one-click XML importer are already host-independent.
