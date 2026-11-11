# Storylens editor interchange tools

See [the current editor handoff and validation record](../../docs/editor-link-workflow-2026-11-04.md) for native results, project paths, and remaining routes.

- `send_to_resolve.py` captures an active Premiere sequence using the existing connected Storylens panel. It imports original media using XML or uses an explicit compatibility render. It requires a running, activated Resolve session. The SDK-triggered render is awaiting a native test.
- `resolve_handoff.py` imports existing XML into a separate Resolve project. `--compound` groups all native video, audio and transition items after timing verification.
- `to_capcut.py` prepares a local editable draft from supported timeline XML. `from_capcut.py` converts supported local drafts back to XML. CapCut native playback and visual effect parity require separate checks.
- `to_after_effects.py` prepares a guarded JSX to run in After Effects. Live execution of this generated script is pending.
- `cache_to_xml.py` wraps an existing picture/audio file with XML without another encode.

Use each command with `--help` for its inputs. Preserve editor originals and create a new output folder for each distinct transfer. A rendered cache carries the source editor’s rendered look and sound as media. An editable interchange carries the media and properties that the receiving editor can reconstruct. There is no shared Storylens UI button for these prototypes.
