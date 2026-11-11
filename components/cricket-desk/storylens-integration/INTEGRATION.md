
## Storylens feature integration — 4 November 2026

Cricket Desk is now in the Storylens WEB feature menu: Show tools > Cricket Desk, beside Photo Collector. Direct entry: http://127.0.0.1:8765/?tool=cricketDesk. It opens the existing http://127.0.0.1:8879/ inbox in a single tool iframe, sharing the same saved database, selections and enabled schedule. There is no duplicate collector, new GPT run, worker restart, planner-model change or publication. Native Adobe CEP menus were not changed.

Actual running Storylens browser verification confirmed the feature is searchable/clickable and renders the real 80-candidate inbox with both feed/GPT switches checked. Source-description registration was corrected after a real feature-switch error; no later error appeared in captured logs. Automated clicks inside the cross-origin inbox iframe were unavailable (click/focus target errors), so embedded Settings interaction was not independently accepted in this integration pass. The same inbox's standalone Settings/search/selection checks passed in the earlier UI pass. Keep this scope distinction. Screenshot and detailed receipt: D:/Workflow_Automation/cricket-meme-inbox/storylens-integration/.

The existing Windows sign-in launcher starts Cricket Desk. If its service is stopped, open D:/Workflow_Automation/cricket-meme-inbox/Launch Cricket Desk.vbs. Do not start/restart Storylens merely to inspect this integration: static files are served without a restart.
