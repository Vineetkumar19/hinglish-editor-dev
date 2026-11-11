# Export contents and privacy

The package contains the current authored application modules, frontend sources, native integration scripts, tests, build and dependency manifests, documentation and selected required UI assets for the seven components.

## External setup materials

Model weights, generated videos, local virtual environments, node_modules, downloaded third-party runtime installations, SDK installations and restricted sound/media libraries remain external setup dependencies. Their metadata and source references should be reviewed in docs/MODELS.md and the component requirement files.

## Personal state

Production environment files, OAuth client-secret files, browser cookies, pairing credentials, databases, cached conversations, personal finance records, agent profile data, private signing files and active job queues are excluded. Generic .env.example files and fictional test fixtures remain available.

The export applies filename/directory exclusions and pattern-based credential checks. Embedded font/image bytes and negative-test URLs can resemble token strings. Reviewed false-positive matches are recorded separately without replacing the original fixture or asset bytes.

The original components are preserved as a coordinated snapshot. Machine-specific D: paths remain visible where they affect behavior so reviewers can identify the actual portability work.

## Source integrity

docs/file-manifest.json records the SHA-256 and Git blob identity of each exported source file. The local export journal records source paths and scan decisions. The repository contains only review-facing records.

Run scripts/verify_snapshot.py to check manifest entries after downloading. The verification performs read-only file checks.

A historical visual-asset choice manifest with signed source URLs is omitted from the review package. Its application implementation remains included.
