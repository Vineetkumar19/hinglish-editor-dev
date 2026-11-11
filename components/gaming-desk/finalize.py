from pathlib import Path
import datetime as dt
import json
import shutil
import sys
import urllib.request

root=Path(__file__).parent
guide='''# Gaming Desk — owner workflow, 4 November 2026

The owner requested the same Cricket Desk tool for the gaming channel: newly announced/released games, meaningful updates/patches, trailers, community reactions and memes for future video creation. Never infer that a named game is released merely from the owner's example. Preserve announcement/early-access/full-release/preload/update distinctions and actual platform, region and date.

Storylens WEB menu: Show tools > Gaming Desk. Direct route http://127.0.0.1:8765/?tool=gamingDesk embeds the independent http://127.0.0.1:8880/ inbox. Files/data/media: D:/Workflow_Automation/gaming-meme-inbox. Native Adobe CEP menus are unchanged. No new planner/local model route or platform publishing is added. Cricket Desk's database, settings and accounts are separate.

Owner requested same behaviour as Cricket Desk: feeds and GPT initially ON. Feed interval30min; GPT interval30min18:00–00:00IST (end exclusive), maximum12attempts/day. Manual game/event, automatic discovery, domains, lookback, daily times, dates and caps are independently editable. Gaming and cricket research use separate attempts; never silently duplicate native Codex heartbeat automations. Stop switches remain available. The Windows sign-in shortcut launches Gaming Desk in the background using saved settings; actual reboot/login was not tested.

Public feeds: current publisher announcement RSS from PlayStation Blog, Xbox Wire and Steam; bounded indexed gaming news; Reddit r/gaming, r/Games and r/gamingmemes; indexed Instagram/X direct posts. Selected domains are enforced. Feed publication dates older than the requested lookback or materially future-dated are excluded when parseable; missing dates remain unknown. Generic indexed store pages are not proof of a new game release. The initial overly broad27catalog candidates were archived to data/initial-catalog-scan-archived.json before the improved source pass. Do not treat community claims as confirmed news.

Same owner review controls: To review/Selected/Skipped, source and text filters, original URL/author/date, Save image where accessible, and Export selected with image/source provenance. Memes/news/rumours remain research candidates. No guarantee of all-platform access, complete internet coverage, licensing or monetization. This tool does not publish, bypass login or download every Reel/video.

GPT uses the official installed Codex CLI, the existing ChatGPT login, fixed gpt-6.1-sol and live web search; no new API key or local reasoning model. It is not visible Chrome automation. Prompt budgets8search/read operations (advisory); process timeout10min and daily attempt cap are enforced. Concrete recent publisher-feed links seed research but remain unverified leads. Full article/date verification gates remain. Keep result provenance and clear limitations when sources cannot be opened.

Actual acceptance record: six unit checks passed; live manual-game save/restore, real source image download, temporary Keep/export/restore and standalone Settings/source/search controls verified. Running Storylens feature search/menu click and real inbox render verified, no captured console errors. The updated feed pass produced71deduplicated candidates: official PlayStation/Xbox feeds worked; Steam returned0current announcements; r/Games/r/gamingmemes were rate-limited and indexed X/Instagram returned0direct posts. TWO real GPT passes completed and each returned0verified additions due to source-access/evidence gaps. Do not describe those tests as successful content discovery or invent video angles. No production selection or publication occurred. Inspect validation-result.json and data/research-runs for exact current evidence; do not rerun expired tests or reset current choices from this historical receipt.

Startup/repair: use Launch Gaming Desk.vbs when the inbox service is stopped. Storylens serves the modified static feature registration without a main-service restart. Backups and screenshot: storylens-integration/. Global reference copies do not imply permanent automatic full-context recall.
'''

if '--global' in sys.argv:
 dest=Path('C:/Users/Vineet Kumar/.codex/references/gaming-meme-inbox-20261104')
 dest.mkdir(parents=True,exist_ok=True)
 for name in ['REFERENCE-GUIDE.md','validation-result.json','README.md']:
  shutil.copy2(root/name,dest/name)
 skill=Path('C:/Users/Vineet Kumar/.codex/skills/storylens-workflows/SKILL.md')
 text=skill.read_text(encoding='utf-8')
 section='''
## Gaming meme/news inbox —4November2026

Gaming Desk is installed in the Storylens WEB feature menu beside Cricket Desk: `http://127.0.0.1:8765/?tool=gamingDesk`. Independent inbox/service/data at `D:/Workflow_Automation/gaming-meme-inbox`, port8880. Read `C:/Users/Vineet Kumar/.codex/references/gaming-meme-inbox-20261104/REFERENCE-GUIDE.md` for sources, schedule controls and actual acceptance. Same editable feed/GPT controls, initially ON (feeds30min; GPT30min18:00–00:00IST,12attempts/day), manual game focus and selected-image/source export. GPT is official ChatGPT-authenticated Sol live-web research, not Chrome automation/local reasoning. Public feed/UI/image-export checks passed; two GPT runs completed with zero verified additions because of source-access/evidence gaps. No publishing or automatic monetization. Native Adobe menus unchanged.
'''
 if '## Gaming meme/news inbox —4November2026' not in text:skill.write_text(text+'\n'+section,encoding='utf-8')
 print('Gaming Desk saved in global Storylens references')
else:
 s=json.load(urllib.request.urlopen('http://127.0.0.1:8880/api/state',timeout=10))
 assert s['config']['enabled'] and s['config']['gpt_enabled'] and not s['gpt_running']
 p=root/'validation-result.json';r=json.loads(p.read_text(encoding='utf-8'))
 r.update(checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),candidate_count=len(s['items']),feed_sources=s['last_scan'],gpt_receipt=s['gpt_receipt'],gpt_tests=[{'folder':str(f.parent),'result':json.loads(f.read_text(encoding='utf-8'))}for f in (root/'data/research-runs').glob('*/result.json')],browser_checks=['standalone Settings open/close','News source filter','Xbox search filter','Storylens Gaming Desk search and menu click','real embedded inbox render','no captured console errors'],startup_shortcut_verified=True,actual_reboot_tested=False,task_ui_actions_finished=True)
 p.write_text(json.dumps(r,indent=2),encoding='utf-8')
 (root/'REFERENCE-GUIDE.md').write_text(guide,encoding='utf-8')
 p=root/'storylens-integration/installation.json';i=json.loads(p.read_text(encoding='utf-8'));i.update(browser_validation='Verified feature search/menu activation and real inbox render',screenshot=str(root/'storylens-integration/feature-visible.png'));p.write_text(json.dumps(i,indent=2),encoding='utf-8')
 print(json.dumps({'candidates':len(s['items']),'gpt_test_status':s['gpt_receipt']['status'],'verified_gpt_additions':s['gpt_receipt']['new_items'],'ui_verified':True}))
