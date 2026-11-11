"""The evaluator: a local vision model (Ollama qwen2.5vl) looks at every AI picture / clip and fails the ones that
do not show what was asked or look broken (melted faces, extra fingers, garbled text, a real logo)."""
from dataclasses import asdict, dataclass, field
import hashlib
from hinglish_cut.ollama_gpu import post as gpu_ollama_post
import json
from pathlib import Path

import requests
from PIL import Image

from hinglish_visuals.brain import OLLAMA_URL, ollama_models
from hinglish_visuals.evaluator import VISION_MODEL, _for_model, _png64

JUDGE_SYSTEM = '''You check an AI-generated {what} for a video. It was asked to show:
"{prompt}"
Answer honestly:
- shows_request: does it clearly show that (main subject, action and setting)?
- broken: are faces, hands, bodies or objects deformed / melted / with extra limbs or fingers?
- bad_text: is there garbled, misspelled or nonsense text or letters?
- real_logo_or_celebrity: does it show a real brand logo or a recognisable famous real person?
- score: 1-10 overall quality for use in a professional video.
- problem: the main problem in a few words ("" if none).'''
JUDGE_SCHEMA = {'type': 'object', 'properties': {
    'seen': {'type': 'string'}, 'shows_request': {'type': 'boolean'}, 'broken': {'type': 'boolean'},
    'bad_text': {'type': 'boolean'}, 'real_logo_or_celebrity': {'type': 'boolean'},
    'score': {'type': 'integer'}, 'problem': {'type': 'string'}},
    'required': ['seen', 'shows_request', 'broken', 'bad_text', 'real_logo_or_celebrity', 'score', 'problem']}


@dataclass
class Verdict:
    passed: bool | None
    score: float = 0.0
    reasons: list = field(default_factory=list)
    seen: str = ''

    def to_dict(self):
        return asdict(self)


def decide(answer):
    reasons = []
    if not answer.get('shows_request', False):
        reasons.append('does not show what was asked')
    if answer.get('broken'):
        reasons.append('deformed faces/hands/objects')
    if answer.get('bad_text'):
        reasons.append('garbled text')
    if answer.get('real_logo_or_celebrity'):
        reasons.append('real logo or famous person')
    score = int(answer.get('score') or 0)
    if score and score < 5:
        reasons.append(f'low quality ({score}/10)')
    if answer.get('problem') and reasons:
        reasons.append(str(answer['problem'])[:80])
    return Verdict(not reasons, float(score), reasons, str(answer.get('seen', ''))[:200])


class Judge:
    def __init__(self, root, model=VISION_MODEL, url=OLLAMA_URL):
        from hinglish_cut.model_preferences import resolve_model
        model = resolve_model(root, 'vision_model', model, VISION_MODEL)
        self.root = Path(root)
        self.model, self.url = model, url.rstrip('/')
        self.cache = Path(root) / 'cache' / 'aigen' / 'judge'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.trust_env = False
        names = ollama_models(self.session, self.url)
        if model not in names and model + ':latest' not in names:
            raise RuntimeError(f'Ollama is missing {model} (run: ollama pull {model})')
        self.name = f'{model} (looks at every picture)'

    def _ask(self, images, what, prompt):
        pictures = [_png64(_for_model(im)) for im in images]
        system = JUDGE_SYSTEM.format(what=what, prompt=prompt)
        key = hashlib.sha256(json.dumps([self.model, system, pictures]).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        body = {'model': self.model, 'stream': False, 'format': JUDGE_SCHEMA,
                'options': {'temperature': 0, 'seed': 3, 'num_ctx': 8192, 'num_predict': 400},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': 'Check this.', 'images': pictures}]}
        from hinglish_cut.model_preferences import configure_request
        configure_request(self.root, body)
        from hinglish_cut.feature_context import configure as feature_context, record as record_context
        record_context(self.root, feature_context(self.root,body,'thumbnail',kind='vision'))
        response = gpu_ollama_post(self.root, self.session, self.url + '/api/chat', json=body, timeout=1800)
        response.raise_for_status()
        answer = json.loads((response.json().get('message') or {}).get('content') or '{}')
        file.write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding='utf-8')
        return answer

    def image(self, path, prompt):
        try:
            with Image.open(path) as im:
                picture = im.convert('RGB')
        except Exception:
            return Verdict(False, 0.0, ['the file is not a readable picture'])
        return decide(self._ask([picture], 'picture', prompt))

    def video(self, path, prompt, samples=3):
        from hinglish_broll.library import probe_video, read_frames
        try:
            seconds = probe_video(path)[0]
            frames = [im for _, im in read_frames(path, [seconds * (k + .5) / samples for k in range(samples)], size=768)]
        except Exception:
            frames = []
        if not frames:
            return Verdict(False, 0.0, ['the clip could not be opened'])
        return decide(self._ask(frames, f'video clip ({len(frames)} frames of one clip)', prompt))

    def close(self):
        self.session.close()


def open_judge(root, progress=print):
    try:
        return Judge(root)
    except Exception as error:
        progress(f'  Evaluator off: {error}')
        return None
