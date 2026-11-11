# AI Editor — StoryLens source review

Private review snapshot prepared on 11 November 2026. This repository contains the current local source for StoryLens and its connected projects.

## Start here

1. Read [the manager guide](docs/REVIEW-GUIDE.md).
2. Follow [the architecture and main request flows](docs/ARCHITECTURE.md).
3. Pick any feature in [the feature index](docs/FEATURES.md).
4. Use [the source maps](docs/SOURCE-MAPS.md) to inspect module definitions line by line.
5. Read [setup and compatibility](docs/SETUP.md), [models](docs/MODELS.md), and [review limits](docs/REVIEW-STATUS.md).

## Projects included

| Project | Source | Role |
| --- | --- | --- |
| StoryLens | [components/storylens](components/storylens) | Editor UI, media jobs, native integrations, voice integration, analytics and finance summary |
| Cortana runtime | [components/cortana-runtime](components/cortana-runtime) | Shared speech and Windows application-control implementation used by StoryLens |
| Agent Suite | [components/agents](components/agents) | Editing clients, sponsorships, SaaS sales, development clients, jobs, community and review queues |
| Pocket Tracker | [components/pocket-tracker](components/pocket-tracker) | Android ledger and authenticated laptop companion |
| Finance Tracker | [components/finance-tracker](components/finance-tracker) | React UI, local ledger API, analytics and investment records |
| Cricket Desk | [components/cricket-desk](components/cricket-desk) | Cricket research and selected asset inbox |
| Gaming Desk | [components/gaming-desk](components/gaming-desk) | Gaming research and selected asset inbox |

Cortana remains a separately maintained project. This snapshot includes its source as a dependency for review. The original projects on the owner's computer have not been merged or replaced.

## Review scope

This is a source snapshot with setup notes, original tests, source maps, and feature guides. The guides describe source behavior and identify live dependencies. A fresh installation on either manager's laptop has not been accepted as working.

Large model weights, virtual environments, downloaded tools, private records, account sessions, and restricted media libraries require separate setup. See [the export notes](docs/EXPORT.md) and [file manifest](docs/file-manifest.json).

Previous Git history is retained. The default-branch tree has been refreshed with this review layout.
