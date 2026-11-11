"""Verify the finished portable memory against the canonical reference library."""
import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hinglish_niche.documentary_memory import RELATIVE,STYLES
from hinglish_niche.style_memory import search

OUT=ROOT/'output/reference-analysis/continuous-documentary-memory'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def main():
    package=OUT/'DOCUMENTARY_MEMORY_PORTABLE.zip'
    manifest=read(package.with_suffix('.manifest.json'))
    quality=read(OUT/'memory-quality-receipt.json')
    digest=hashlib.sha256()
    with package.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):
            digest.update(block)
    if digest.hexdigest()!=manifest['sha256']:
        raise ValueError('Portable archive hash mismatch')
    backup=OUT/'archive-verification.sqlite3'
    try:
        with zipfile.ZipFile(package) as archive:
            damaged=archive.testzip()
            if damaged:
                raise ValueError('Damaged portable archive entry: '+damaged)
            names=archive.namelist()
            if any(Path(name).suffix.lower() in ('.mp4','.mkv','.mov','.gguf','.safetensors') for name in names):
                raise ValueError('Original video or model weights unexpectedly packaged')
            saved=read(ROOT/RELATIVE/'manifest.json')
            for brain in saved['brains']:
                if hashlib.sha256(archive.read(brain['file'])).hexdigest()!=brain['sha256']:
                    raise ValueError('Full brain snapshot changed in archive')
            for source in quality['sources']:
                base='cricket-documentaries' if source['style']==STYLES[0] else 'crick-edit-editing-style'
                for frame in (ROOT/'output/reference-analysis'/base/source['slug']/'scene-keyframes').glob('*.jpg'):
                    if frame.relative_to(ROOT).as_posix() not in names:
                        raise ValueError('Source scene reference missing: '+str(frame))
                if source['audio_available']:
                    expected=f'output/reference-analysis/{base}/{source["slug"]}/audio-features.npy'
                    if expected not in names:
                        raise ValueError('Detailed audio evidence missing: '+expected)
            backup.write_bytes(archive.read('library/creator-profiles/editing-dna.sqlite3'))
        connection=sqlite3.connect(backup)
        try:
            if connection.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise ValueError('SQLite portable backup integrity failure')
            counts=[]
            for style in STYLES:
                expected=sum(s['indexed_seconds'] for s in quality['sources'] if s['style']==style)
                actual=connection.execute('SELECT COUNT(*) FROM records WHERE style=? AND kind=?',(style,'continuous-motion-second')).fetchone()[0]
                vectors=connection.execute('SELECT COUNT(*) FROM records WHERE style=? AND kind=? AND embedding IS NOT NULL AND model=?',(style,'continuous-motion-second','intfloat/multilingual-e5-small')).fetchone()[0]
                guidance=connection.execute('SELECT COUNT(*) FROM records WHERE style=? AND kind=?',(style,'brain-guidance')).fetchone()[0]
                if actual!=expected or vectors!=expected or guidance<2:
                    raise ValueError('Incomplete memory records or vectors: '+style)
                counts.append({'style':style,'seconds':actual,'vectors':vectors,'brain_passages':guidance})
        finally:
            connection.close()
    finally:
        if backup.exists():
            backup.unlink()
    retrieval=[]
    for style in STYLES:
        rows=search(ROOT,style,'camera travel push-in zoom parallax moving image',limit=2,kinds=['continuous-motion-second'])
        if not rows or any(not r['id'].startswith(style+'/') or 'motion' not in r['data'] for r in rows):
            raise ValueError('Actual motion retrieval failed: '+style)
        with patch('hinglish_niche.style_memory._embedder',side_effect=OSError('Encoder deliberately unavailable for verification')):
            fallback=search(ROOT,style,'camera',limit=2)
        if not fallback or any(r.get('retrieval_method')!='keyword fallback' for r in fallback):
            raise ValueError('Actual encoder-free retrieval failed: '+style)
        retrieval.append({'style':style,'vector_retrieval':'passed','keyword_fallback':'passed',
            'source_examples':[{'source':r['source'],'start':r['start']} for r in rows]})
    result={'status':'passed','native_frames':quality['native_frames'],
        'reference_seconds':quality['video_seconds'],'indexed_seconds':quality['visual_semantic_seconds'],
        'archive_bytes':package.stat().st_size,'archive_sha256':digest.hexdigest(),
        'archive_entries':len(names),'sqlite_integrity':'ok','database':counts,'retrieval':retrieval,
        'original_videos_or_weights_in_archive':False}
    (OUT/'archive-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
