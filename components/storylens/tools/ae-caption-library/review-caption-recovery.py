"""Safe final probes against saved evidence. No model, AE or owner-file changes."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from uroman import Uroman
from hinglish_app.template_text_model import speech_normal,align_script
from hinglish_app.caption_native_match import reconcile
from hinglish_app.caption_native_timing import align_words
from hinglish_app.caption_audio_alignment import check_relation
from hinglish_app.caption_recognition_recovery import stitch
from hinglish_app.caption_numbers import comparison_key
r=Uroman();norm=lambda t:speech_normal(r.romanize_string(t,lcode='hin'))
folder=root/'output/captions/ae-speech/028e1eda1e6a4c12982ca295c5be8a26'
request=json.loads((folder/'request.json').read_text('utf8'))
observed=json.loads((root/'cache/caption-native-timing/a86cb004296c0ce8a6a6a4d317ff521316e7c57ceb77c6896a1b3b0dcfed35a8/observed-window-recovery-v1.json').read_text('utf8'))
checks=[]
def probe(name,fn):
    try:fn();checks.append({'name':name,'passed':True})
    except Exception as e:checks.append({'name':name,'passed':False,'details':str(e)})
def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')
def relation(script):
    check_relation(script.split(),reconcile(script,observed,norm,align_script),observed,norm)
probe('Unrelated script remains rejected after complete audio retry',lambda:reject(lambda:relation('Gardening flowers watering seeds blossom sunshine plants pruning')))
probe('Incorrect price remains rejected',lambda:reject(lambda:relation(request['script'].replace('60 rupaye','61 rupaye'))))
probe('Correct 3–4 range is not interpreted as 34',lambda:reject(lambda:relation(request['script'].replace('3–4','34'))))
probe('NaN timing cannot enter captions',lambda:reject(lambda:align_words('hello',[{'text':'hello','start':float('nan'),'end':1}],2)))
probe('Negative timing cannot enter captions',lambda:reject(lambda:align_words('hello',[{'text':'hello','start':-1,'end':1}],2)))
def decimals():
    assert comparison_key('3.4',norm)!=comparison_key('34',norm)
    assert comparison_key('0.05',norm)!=comparison_key('0.5',norm)
probe('Decimal values stay distinct',decimals)
probe('Correct actual script still satisfies relationship checks',lambda:relation(request['script']))
receipt={'checks':checks,'new_findings':[c for c in checks if not c['passed']],
 'known_unfixed_findings':['Previously reported internal boolean acoustic timestamps are still accepted by validate_aligned; unchanged in this repair.'],
 'limits':['Native AE playback is owner testing, as explicitly requested.','Eleven Rapido caption tokens and six housing caption tokens have uncertain acoustic timing; not claimed speech-sync accepted.','Unrecognized vocabulary, unsupported spoken number forms and noisy audio can still require review; no arbitrary-input guarantee.']}
(root/'output/caption-recording-recovery-20261029/final-review.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps(receipt));sys.exit(bool(receipt['new_findings']))
