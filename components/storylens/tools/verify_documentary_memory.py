"""Run focused memory/planning regressions and record the live renderer check."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/reference-analysis/continuous-documentary-memory'


def cases(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):
            yield from cases(item)
        elif 'RenderTest' not in item.id():
            yield item


def main():
    suite=unittest.TestLoader().loadTestsFromNames([
        'tests.test_niche','tests.test_motion','tests.test_documentary',
        'tests.test_creator_memory','tests.test_continuous_documentary_memory',
        'tests.test_reference_dna','tests.test_documentary_sets'])
    with (OUT/'final-tests.log').open('w',encoding='utf8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(cases(suite)))
    receipt={'status':'passed' if result.wasSuccessful() else 'failed',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'scope':'Documentary analysis, shared model memory, export, existing motion planning and profile isolation; full browser-render test classes excluded from this suite.'}
    receipt['live_renderer']=json.loads((OUT/'browser-smoke/result.json').read_text(encoding='utf8'))
    (OUT/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt,indent=2),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
