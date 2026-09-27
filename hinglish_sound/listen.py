"""The ears: CLAP (a local audio-text model) LISTENS to every sound and music file, so choices are made by
what a file actually sounds like, not by its file name.

- audio vectors: search "deep cinematic boom" and get files that sound like one
- "sounds like" labels for every file (from a fixed vocabulary), shown to the AI director
- music facts: singing or instrumental, energy, tempo
Everything is cached per file; the model downloads once into models/ (about 0.8 GB) and runs on CPU."""
import hashlib
import json
from pathlib import Path

import numpy as np

from .library import decode

CLAP_MODEL = 'laion/larger_clap_general'
RATE = 48000
WINDOW = 7.0            # seconds of audio per embedding (CLAP hears up to 10 s)
BATCH = 8               # files per model pass when listening to a library for the first time

# What a sound can be. The top matches become the file's "sounds like" label for the AI.
SFX_VOCAB = {
    'whoosh': 'a fast whoosh swoosh of air passing by',
    'boom': 'a deep cinematic boom impact with bass',
    'hit': 'a punchy hit impact sound effect',
    'bass drop': 'a heavy sub bass drop',
    'riser': 'a rising tension riser building up',
    'reverse swell': 'a reverse cymbal swell',
    'pop': 'a short bubble pop sound',
    'click': 'a mouse click or button tap',
    'notification': 'a phone notification ping',
    'message': 'a message sent swoosh or chat bubble sound',
    'typing': 'keyboard typing sounds',
    'camera': 'a camera shutter click',
    'cash': 'a cash register or coins money sound',
    'ding': 'a bright ding chime bell',
    'sparkle': 'a magical sparkle twinkle',
    'success': 'a positive success jingle',
    'fail': 'a failure buzzer wrong answer sound',
    'record scratch': 'a vinyl record scratch',
    'cartoon': 'a silly cartoon comedy sound effect like a boing or slide whistle',
    'game': 'an 8-bit retro video game sound',
    'heartbeat': 'a slow heartbeat thump',
    'ticking': 'a clock ticking',
    'drone': 'a dark ambient drone',
    'glitch': 'a digital glitch stutter static',
    'poof': 'a poof vanish disappear sound',
    'applause': 'people clapping applause',
    'laugh': 'people laughing',
    'crowd': 'crowd noise ambience',
    'voice': 'a person talking',
    'animal': 'an animal sound like a dog barking',
    'music': 'a piece of music',
}
MUSIC_VOCAB = {
    'calm piano': 'calm solo piano music',
    'emotional strings': 'emotional slow string orchestra music',
    'lo-fi': 'relaxed lo-fi hip hop beat',
    'upbeat pop': 'happy upbeat pop instrumental with drums',
    'cinematic': 'epic cinematic orchestral music',
    'tense': 'tense suspenseful dark music',
    'ambient': 'soft ambient atmospheric pad music',
    'acoustic': 'warm acoustic guitar music',
    'electronic': 'energetic electronic dance beat',
    'funny': 'quirky funny comedic music',
    'indian': 'indian classical music with sitar and tabla',
    'corporate': 'light corporate background music',
}
SINGING = 'a song with a person singing lyrics'
INSTRUMENTAL = 'instrumental background music without any singing'
CARTOON = SFX_VOCAB['cartoon']
CINEMATIC = 'a clean professional cinematic sound effect'


def _key(path, extra=''):
    p = Path(path)
    stat = p.stat()
    return hashlib.sha1(json.dumps([str(p.resolve()), stat.st_size, int(stat.st_mtime), extra]).encode()).hexdigest()


def sfx_window(path):
    """Mono 48 kHz, up to WINDOW s centred on the loudest part (what the listener hears of the effect)."""
    audio = decode(path, RATE, mono=True, limit=12)[0]
    if len(audio) <= WINDOW * RATE:
        return audio
    hop = int(.05 * RATE)
    energy = np.add.reduceat(audio ** 2, np.arange(0, len(audio), hop))
    peak = int(np.argmax(energy)) * hop
    start = max(0, min(len(audio) - int(WINDOW * RATE), peak - int(WINDOW * RATE / 3)))
    return audio[start:start + int(WINDOW * RATE)]


def music_windows(path, count=3):
    """Three WINDOW-second slices (early, middle, late) of a track, mono 48 kHz."""
    audio = decode(path, RATE, mono=True, limit=240)[0]
    n = int(WINDOW * RATE)
    if len(audio) <= n:
        return [audio]
    starts = [int((len(audio) - n) * f) for f in (.15, .5, .8)][:count]
    return [audio[s:s + n] for s in starts]


def music_features(path):
    """Energy (0-1: how busy/loud it moves) and tempo (BPM estimate) from the audio itself."""
    audio = decode(path, 16000, mono=True, limit=90)[0]
    if len(audio) < 16000 * 4:
        return {'energy': 0.0, 'bpm': 0.0}
    hop = 320                                                 # 20 ms
    frames = np.lib.stride_tricks.sliding_window_view(audio, 640)[::hop]
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    flux = np.maximum(0, np.diff(rms))                        # onsets: where loudness jumps
    onset_rate = float((flux > flux.mean() + 2 * flux.std()).mean() * 50)    # onsets per second
    dynamics = float(np.std(20 * np.log10(rms + 1e-9)) / 12)
    energy = float(np.clip(.6 * min(1, onset_rate / 4) + .4 * min(1, dynamics), 0, 1))
    env = flux - flux.mean()
    ac = np.correlate(env, env, 'full')[len(env) - 1:]
    lo, hi = int(50 * 60 / 180), int(50 * 60 / 60)            # 60-180 BPM at 50 frames/s
    lag = lo + int(np.argmax(ac[lo:hi])) if hi < len(ac) else 0
    return {'energy': round(energy, 2), 'bpm': round(60 * 50 / lag) if lag else 0.0}


class Listener:
    """CLAP audio-text embeddings, cached per file."""

    def __init__(self, root, model=CLAP_MODEL, device='cpu', threads=4, backend=None):
        self.cache = Path(root) / 'cache' / 'sound' / 'clap'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.model_name = model
        if backend is not None:                   # tests and other models: needs .texts() and .audio()
            self.backend = backend
            return
        import torch
        from transformers import ClapModel, ClapProcessor
        from hinglish_broll.vision import model_folder
        torch.set_num_threads(threads)
        self.torch = torch
        self.device = 'cuda' if device == 'cuda' and torch.cuda.is_available() else 'cpu'
        folder = model_folder(model, root)
        self.model = ClapModel.from_pretrained(folder).to(self.device).eval()
        self.processor = ClapProcessor.from_pretrained(folder)
        self.backend = self

    # ---- model calls (real CLAP) ----
    def _norm(self, x):
        x = x.float().cpu().numpy()
        return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)

    def texts(self, texts):
        with self.torch.no_grad():
            inputs = self.processor(text=list(texts), return_tensors='pt', padding=True).to(self.device)
            return self._norm(self.model.get_text_features(**inputs))

    def audio(self, clips):
        with self.torch.no_grad():
            clips = [np.asarray(c, np.float32) for c in clips]
            try:            # newer transformers call it `audio`, older `audios`
                inputs = self.processor(audio=clips, sampling_rate=RATE, return_tensors='pt')
                if 'input_features' not in inputs:
                    raise ValueError('no audio features')
            except (TypeError, ValueError):
                inputs = self.processor(audios=clips, sampling_rate=RATE, return_tensors='pt')
            return self._norm(self.model.get_audio_features(**inputs.to(self.device)))

    # ---- cached, per file ----
    def text_vectors(self, texts):
        return self.backend.texts(texts)

    def _cache_file(self, path, kind):
        return self.cache / f'{_key(path, self.model_name + kind)}.npy'

    @staticmethod
    def _clips(path, kind):
        clips = [sfx_window(path)] if kind == 'sfx' else music_windows(path)
        return [c for c in clips if len(c) >= RATE * .05] or [np.zeros(int(RATE * .1), np.float32)]

    def _save(self, path, kind, rows):
        vector = np.asarray(rows).mean(axis=0)
        vector = vector / max(float(np.linalg.norm(vector)), 1e-8)
        np.save(self._cache_file(path, kind), vector.astype(np.float32))
        return vector

    def file_vector(self, path, kind):
        file = self._cache_file(path, kind)
        if file.exists():
            return np.load(file)
        return self._save(path, kind, self.backend.audio(self._clips(path, kind)))

    def vectors(self, assets, progress=print, batch=BATCH):
        """One vector per file. New files are listened to several at a time (one model pass per batch),
        which is several times faster than one by one on a CPU; a file that fails is retried alone."""
        out = [None] * len(assets)
        todo = []
        for i, asset in enumerate(assets):
            try:
                file = self._cache_file(asset.path, asset.kind)
                if file.exists():
                    out[i] = np.load(file)
                    continue
            except Exception:
                continue
            todo.append(i)
        done = 0
        for s in range(0, len(todo), batch):
            chunk = todo[s:s + batch]
            if done == 0 or done // 40 != (done + len(chunk)) // 40 or s + batch >= len(todo):
                progress(f'  Listening to your {assets[chunk[0]].kind} library {done + len(chunk)}/{len(todo)} new files '
                         '(first time only)')
            done += len(chunk)
            clips, owners = [], []
            for i in chunk:
                try:
                    parts = self._clips(assets[i].path, assets[i].kind)
                except Exception:
                    continue
                clips += parts
                owners += [i] * len(parts)
            if not clips:
                continue
            try:
                rows = self.backend.audio(clips)
            except Exception:
                rows = None
            for i in dict.fromkeys(owners):
                try:
                    if rows is None:
                        out[i] = self.file_vector(assets[i].path, assets[i].kind)
                    else:
                        out[i] = self._save(assets[i].path, assets[i].kind,
                                            [rows[k] for k, o in enumerate(owners) if o == i])
                except Exception:
                    out[i] = None
        dim = next((v.shape[0] for v in out if v is not None), 512)
        return np.stack([v if v is not None else np.zeros(dim, np.float32) for v in out]) if out else \
            np.zeros((0, dim), np.float32)

    def describe(self, vectors, kind, top=3):
        """'sounds like' labels for each file from the fixed vocabulary, plus facts the rules need."""
        vocab = SFX_VOCAB if kind == 'sfx' else MUSIC_VOCAB
        names = list(vocab)
        extra = [CARTOON, CINEMATIC] if kind == 'sfx' else [SINGING, INSTRUMENTAL]
        texts = self.text_vectors([vocab[n] for n in names] + extra)
        sims = vectors @ texts.T
        rows = []
        for s in sims:
            labels = [names[i] for i in np.argsort(-s[:len(names)])[:top]]
            a, b = float(s[-2]), float(s[-1])
            row = {'sounds_like': labels}
            if kind == 'sfx':
                row['cartoonish'] = a > b + .03
            else:
                row['vocals'] = a > b + .03
            rows.append(row)
        return rows

    def similarity(self, vector, texts):
        return self.text_vectors(texts) @ vector
