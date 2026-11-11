"""Isolated regression comparison; never changes running application sources."""
import io
import json
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hinglish_app import assistant_plan

new='''from below). Default visuals_search_method=website: search public websites for image/PNG options,
without stock API keys or local Vision approval. The human selects the final assets. Use five choices
per keyword for Instagram/vertical and two for YouTube/horizontal. Research people, teams, brands, places,'''
old='''from below). It defaults to five downloaded choices PER named keyword for HUMAN selection, with local
vision checking exact identity AND team/kit/scene context. Research real people, teams, brands, places,'''
system=assistant_plan.SYSTEM.replace(new,old).replace('a photo of a cricketer does not prove a claimed score. These are unverified suggestions, not factual proof.',
    'a photo of a cricketer does not prove a claimed score. Missing verified choices stay empty.')
assert system!=assistant_plan.SYSTEM
values={k:v for k,v in assistant_plan.OPTION_VALUES.items() if k!='visuals_search_method'}
suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_assistant','tests.test_assistant_contracts','tests.test_assistant_creative_tools'])
stream=io.StringIO()
with patch.object(assistant_plan,'SYSTEM',system),patch.object(assistant_plan,'OPTION_VALUES',values):
    result=unittest.TextTestRunner(stream=stream,verbosity=0).run(suite)
folder=Path('output/visuals/website-manual-app-evidence-20261029');folder.mkdir(exist_ok=True,parents=True)
(folder/'assistant-baseline.txt').write_text(stream.getvalue(),encoding='utf-8')
record={'scope':'Same regression suite with only this task\'s Smart Visuals prompt/schema additions removed in process memory; source files unchanged.',
    'tests':result.testsRun,'failures':[t.id() for t,_ in result.failures],'errors':[t.id() for t,_ in result.errors]}
(folder/'assistant-baseline.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
