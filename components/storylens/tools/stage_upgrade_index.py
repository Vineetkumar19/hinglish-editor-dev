"""Prepare verified replacement vectors while other models download; live DB stays unchanged."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STORE = Path(r'C:\Ai Models')
sys.path.insert(0, str(ROOT))


def main():
    state = json.loads((ROOT/'downloads/model-upgrade-c-drive.json').read_text())
    selected = state['models']['embedding']
    proof = json.loads((STORE/'logs/upgrade-validation-embedding.json').read_text())
    assert selected['status'] == 'downloaded' and proof['passed']
    assert proof['model_path'] == selected['path'] and proof['model_revision'] == selected['revision']
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.ollama_embeddings import OllamaEmbeddings
    from hinglish_cut.upgrade_embeddings import StagedEmbeddings
    from hinglish_cut.model_preferences import release_ollama
    source = ROOT/'library/creator-profiles/editing-dna.sqlite3'
    with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as db:
        rows = db.execute('SELECT DISTINCT text FROM records WHERE model=?',
                          ('intfloat/multilingual-e5-small',)).fetchall()
    encoder = StagedEmbeddings(STORE/'cache/upgraded-style-embeddings.sqlite3',
        OllamaEmbeddings(ROOT, 'storylens-embedding:8b-q6'), selected['revision'])
    with gpu_lock(ROOT): release_ollama(ROOT)
    try:
        for start in range(0, len(rows), 16):
            with gpu_lock(ROOT):
                encoder.encode([text for text, in rows[start:start+16]])
            print(f'STAGED {min(start+16,len(rows))}/{len(rows)} unique reference texts', flush=True)
            # Give waiting model checks/editor jobs a chance to take the GPU.
            # Longer than the lock retry interval, so a waiting validation or
            # editor process cannot repeatedly miss this handoff window.
            time.sleep(.3)
    finally:
        with gpu_lock(ROOT): encoder.close()
    print('STYLE_VECTORS_STAGED_LIVE_DATABASE_UNCHANGED', flush=True)


if __name__ == '__main__': main()
