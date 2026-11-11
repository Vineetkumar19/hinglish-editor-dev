from pathlib import Path
import json,sys,time
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from hinglish_app.caption_audio_alignment import align_from_audio
from hinglish_app.template_text_model import speech_normal
from hinglish_cut.model_storage import role
from hinglish_cut.gpu_lock import gpu_lock
from uroman import Uroman
p=root/'output/caption-one-general-speech-20261029';fixture=json.loads((root/'tests/fixtures/caption-native-pg-hinglish.json').read_text('utf8'));u=Uroman();normal=lambda s:speech_normal(u.romanize_string(s,lcode='hin'))
def progress(stage,percent):print(stage,round(percent,1),flush=True)
print('Waiting for the shared processing slot',flush=True);begin=time.monotonic()
try:
 with gpu_lock(root):words=align_from_audio(role(root,'independent_asr')['path'],root/'cache/caption-native-timing/447fb02f763e6fb4914dfed024cba6e8455a87259f048059e6c0e57a01075c5e/narration.wav',fixture['script'],fixture['observed'],fixture['duration'],normal,progress)
 result={'ok':True,'seconds':time.monotonic()-begin,'words':words}
except Exception as error:result={'ok':False,'error':str(error),'seconds':time.monotonic()-begin}
(p/'full-direct-alignment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print({k:v for k,v in result.items() if k!='words'},flush=True)
