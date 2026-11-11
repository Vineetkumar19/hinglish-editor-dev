"""Bounded, declarative per-layer processing. No plugins or executable expressions."""
import math
import numpy as np
import torch
import torchaudio.functional as AF

BOUNDS = {'pan':(-.75,.75), 'highpass_hz':(30.,800.), 'lowpass_hz':(1000.,20000.),
          'speech_pocket_db':(-9.,0.), 'fade_in':(0.,.5), 'fade_out':(0.,2.), 'duck_db':(0.,12.)}


def schema():
    return {'type':'object','properties':{**{key:{'type':'number','minimum':lo,'maximum':hi}
            for key,(lo,hi) in BOUNDS.items()},'why':{'type':'string','maxLength':180}},'additionalProperties':False}


def validate(spec):
    if not isinstance(spec,dict) or set(spec)-set(BOUNDS)-{'why'}:
        raise ValueError('Sound processing contains unsupported settings')
    if not spec:return {}
    why = spec.get('why','')
    if not isinstance(why,str) or not why.strip() or len(why)>180:
        raise ValueError('Explain how the sound processing supports this moment')
    for key,value in spec.items():
        if key == 'why':continue
        lo,hi = BOUNDS[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError('Sound processing setting is outside its supported range: '+key)
    return dict(spec)


def apply(audio, spec, rate=48000):
    spec = validate(spec)
    result = np.asarray(audio,dtype=np.float32).copy()
    if not spec or not result.shape[1]:return result
    tensor=torch.from_numpy(result)
    if 'highpass_hz' in spec:tensor=AF.highpass_biquad(tensor,rate,spec['highpass_hz'])
    if 'lowpass_hz' in spec:tensor=AF.lowpass_biquad(tensor,rate,spec['lowpass_hz'])
    if spec.get('speech_pocket_db'):tensor=AF.equalizer_biquad(tensor,rate,2000.,spec['speech_pocket_db'],.7)
    result=tensor.numpy()
    pan=spec.get('pan',0.)
    if pan and result.shape[0]==2:
        angle=(pan+1)*np.pi/4
        result=result*np.array([np.cos(angle),np.sin(angle)],np.float32)[:,None]*np.sqrt(2.)
    return result.astype(np.float32,copy=False)
