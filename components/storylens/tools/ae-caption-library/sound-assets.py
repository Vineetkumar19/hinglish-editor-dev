"""Bundle the owner's exact pop/click recordings; trim silence, never synthesize replacements."""
from pathlib import Path
import av,numpy as np,json,wave,io,base64,hashlib
root=Path(__file__).resolve().parents[2];base=root/'editor_plugins/caption-3d';out=root/'library/3d-caption-sounds';out.mkdir(exist_ok=True);sr=48000
sources={'pop':Path('D:/Editing/editing assets/main voice/BUBBLE POP SOUND EFFECT - FREE.mp3'),'click':Path('D:/Editing/editing assets/main voice/Click - Sound Effect (HD).mp3')}
# Audited first individual hits in these exact owner recordings. Click's second attack is at ~0.245s.
single_hits={'pop':(1.845,2.030,'bf8d754b35753c11d2ac23a013ad35d0a04b0a79558d4ec8705aae72e8603ddb'),'click':(.115,.215,'c09d48397aed8fa6f9774d104cbe00a0fe0f7b1362791aec4d7a01840672da61')}
def decode(path):
 with av.open(str(path)) as c:
  r=av.AudioResampler(format='fltp',layout='mono',rate=sr);parts=[]
  for f in c.decode(audio=0):parts.extend(x.to_ndarray().reshape(-1) for x in r.resample(f))
  parts.extend(x.to_ndarray().reshape(-1) for x in r.resample(None))
 return np.concatenate(parts)
def encode(a):
 b=io.BytesIO()
 with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(np.round(a*32767).astype('<i2').tobytes())
 return b.getvalue()
old=json.loads((out/'manifest.json').read_text());report={'whoosh':old['whoosh']};assets={};samples={}
whoosh=(out/'whoosh.wav').read_bytes();assets['whoosh']={'sha256':hashlib.sha256(whoosh).hexdigest(),'duration':old['whoosh']['duration'],'base64':base64.b64encode(whoosh).decode()};samples['whoosh']=decode(out/'whoosh.wav')
for name,path in sources.items():
 raw=path.read_bytes();a=decode(path);begin,finish,expected=single_hits[name]
 if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('The owner recording changed; review its first individual hit before rebuilding '+name)
 start=round(begin*sr);end=round(finish*sr);clip=a[start:end];gain=min(1.,.95/max(.0001,float(np.abs(clip).max())));clip=clip*gain;binary=encode(clip);digest=hashlib.sha256(binary).hexdigest();(out/(name+'.wav')).write_bytes(binary)
 assets[name]={'sha256':digest,'duration':len(clip)/sr,'base64':base64.b64encode(binary).decode()};samples[name]=clip
 report[name]={'sha256':digest,'duration':len(clip)/sr,'sample_rate':sr,'channels':1,'peak':float(abs(clip).max()),'source':'Owner-supplied recording; first individual hit, silence trim and linear anti-clipping gain only','hits':1,'source_path':str(path),'source_sha256':hashlib.sha256(raw).hexdigest(),'source_duration':len(a)/sr,'source_start':start/sr,'source_end':end/sr,'linear_gain':gain}
for name,asset in assets.items():
 immutable=out/(asset['sha256']+'.wav');binary=base64.b64decode(asset['base64'])
 if not immutable.exists() or immutable.read_bytes()!=binary:immutable.write_bytes(binary)
(base/'sound-data.jsx').write_text('(function(g){g.StorylensCaptionAudioData='+json.dumps(assets,separators=(',',':'))+';})(typeof $!=="undefined"?$.global:this);',encoding='utf-8');(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
previews=root/'hinglish_app/static/caption-3d-sounds';previews.mkdir(exist_ok=True)
choices={'pop':[('pop',0,1)],'click':[('click',0,1)],'pop_click':[('pop',0,1),('click',.24,.7)],'pop_click_whoosh':[('whoosh',0,.4),('pop',.16,1),('click',.36,.7)]}
for name,events in choices.items():
 duration=max(t+len(samples[k])/sr for k,t,g in events)+.05;audio=np.zeros(round(sr*duration))
 for k,t,g in events:start=round(t*sr);audio[start:start+len(samples[k])]+=samples[k]*g
 audio=audio/max(float(abs(audio).max()),.0001)*.65;(previews/(name+'.wav')).write_bytes(encode(audio))
receipt=root/'output/ae-3d-caption-library/import-single-hit/audio-provenance.json';receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(report,indent=2)+'\n')
print('Bundled one owner Pop and the first owner Click; single-hit auditions. Original MP3s unchanged.')
