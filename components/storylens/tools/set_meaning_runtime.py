"""Register existing verified semantic weights with the laptop's memory settings."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import requests
    from tools.finish_model_upgrade import import_model
    state=json.loads((ROOT/'downloads/model-upgrade-c-drive.json').read_text())
    row=state['models']['meaning']
    assert row['status']=='downloaded'
    session=requests.Session();session.trust_env=False
    for attempt in range(15):
        try:
            session.get('http://127.0.0.1:11434/api/version',timeout=3).raise_for_status()
            break
        except requests.RequestException:
            if attempt==14: raise
            time.sleep(1)
    import_model(session,'meaning',row)
    session.close()


if __name__=='__main__': main()
