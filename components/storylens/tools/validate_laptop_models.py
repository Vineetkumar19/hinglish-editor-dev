"""Run bounded real inference checks; receipts never describe downloads as tests."""
import argparse
import base64
import gc
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('core', 'ollama'), required=True)
    parser.add_argument('--model', default='qwen3.5:9b')
    parser.add_argument('--skip-embedding', action='store_true')
    parser.add_argument('--embedding-only', action='store_true', help='Check the installed sound encoder without rerunning vision/text tests')
    args = parser.parse_args()
    folder = ROOT / 'output/validation/new-laptop'
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / (('embeddings' if args.embedding_only else args.phase) + '-inference.json')
    checks = {}

    def check(name, function):
        print('Checking ' + name, flush=True)
        started = time.monotonic()
        try:
            result = function()
            checks[name] = {'passed': True, 'seconds': round(time.monotonic() - started, 2), 'result': result}
        except Exception as error:
            checks[name] = {'passed': False, 'seconds': round(time.monotonic() - started, 2),
                            'error': f'{type(error).__name__}: {error}'}
            print('  Failed: ' + checks[name]['error'], flush=True)
        receipt.write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
        gc.collect()
        return checks[name]['passed']

    if args.phase == 'ollama':
        import requests
        from PIL import Image, ImageDraw, ImageFont
        session = requests.Session()
        session.trust_env = False
        url = 'http://127.0.0.1:11434'
        def text():
            schema = {'type': 'object', 'properties': {'same': {'type': 'boolean'}, 'reason': {'type': 'string'}},
                      'required': ['same', 'reason']}
            observations = []
            for first, second, expected in [('Maine 40 rupaye diye.', 'Maine 60 rupaye diye.', False),
                                            ('Mujhe editing seekhni hai.', 'Main video edit karna seekhna chahta hoon.', True)]:
                response = session.post(url + '/api/chat', json={'model': args.model, 'stream': False, 'think': False,
                    'format': schema, 'keep_alive': '30s', 'options': {'num_ctx': 12288, 'num_predict': 160, 'temperature': 0},
                    'messages': [{'role': 'system', 'content': 'Compare the intended meaning of two Roman Hinglish sentences. Changed numbers contradict. Natural paraphrases are allowed. Return JSON.'},
                                 {'role': 'user', 'content': json.dumps({'A': first, 'B': second})}]}, timeout=600)
                response.raise_for_status()
                payload = response.json()
                answer = json.loads(payload['message']['content'])
                if answer.get('same') is not expected:
                    raise ValueError('Hinglish number/paraphrase control failed: ' + str(answer))
                observations.append({'answer': answer, 'tokens': payload.get('eval_count'),
                    'tokens_per_second': round(payload.get('eval_count', 0) * 1e9 / max(payload.get('eval_duration', 1), 1), 2)})
            return observations
        if not args.embedding_only:
            check('ollama_hinglish_structured_output', text)
        def vision():
            picture = Image.new('RGB', (640, 384), 'white')
            draw = ImageDraw.Draw(picture)
            draw.ellipse((40, 90, 230, 280), fill='red')
            draw.rectangle((390, 90, 580, 280), fill='blue')
            draw.text((160, 15), 'STORYLENS', fill='black', font=ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 48))
            picture.save(folder / 'vision-control.png')
            buffer = io.BytesIO()
            picture.save(buffer, 'PNG')
            schema = {'type': 'object', 'properties': {key: {'type': 'string'} for key in ('text', 'left', 'right')},
                      'required': ['text', 'left', 'right']}
            response = session.post(url + '/api/chat', json={'model': args.model, 'stream': False, 'think': False,
                'format': schema, 'keep_alive': '30s', 'options': {'num_ctx': 8192, 'num_predict': 160, 'temperature': 0},
                'messages': [{'role': 'user', 'content': 'Read the word at the top and describe the color and shape on the left and right.',
                              'images': [base64.b64encode(buffer.getvalue()).decode()]}]}, timeout=600)
            response.raise_for_status()
            answer = json.loads(response.json()['message']['content'])
            if 'STORYLENS' not in answer.get('text', '').upper() or 'red' not in answer.get('left', '').lower() or 'blue' not in answer.get('right', '').lower():
                raise ValueError('Pixel/OCR control failed: ' + str(answer))
            return {'answer': answer, 'loaded_models': session.get(url + '/api/ps', timeout=10).json()}
        if not args.embedding_only:
            check('ollama_real_image_and_ocr', vision)
        def embeddings():
            response = session.post(url + '/api/embed', json={'model': 'qwen3-embedding:0.6b',
                'input': ['cinematic cricket impact', 'soft piano music'], 'keep_alive': 0}, timeout=300)
            response.raise_for_status()
            rows = response.json()['embeddings']
            if (len(rows) != 2 or len(rows[0]) != 1024 or len(rows[0]) != len(rows[1])
                    or not all(math.isfinite(value) for row in rows for value in row)):
                raise ValueError('Invalid sound embedding vectors')
            norms = [sum(value * value for value in row) ** .5 for row in rows]
            assert all(norm > 0 for norm in norms)
            return {'rows': len(rows), 'dimensions': len(rows[0]), 'norms': norms}
        if not args.skip_embedding:
            check('ollama_sound_embeddings', embeddings)
        session.post(url + '/api/generate', json={'model': args.model, 'keep_alive': 0}, timeout=60)
    else:
        os.environ['HF_HUB_OFFLINE'] = '1'
        import numpy as np
        import torch
        from PIL import Image
        def cuda():
            assert torch.cuda.is_available()
            value = float((torch.ones((32, 32), device='cuda') @ torch.ones((32, 32), device='cuda')).sum().item())
            assert value == 32768
            return {'torch': torch.__version__, 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0),
                    'capability': list(torch.cuda.get_device_capability(0)), 'kernel_result': value}
        if not check('cuda_arithmetic', cuda):
            return 1
        state = json.loads((ROOT / 'downloads/laptop-model-downloads.json').read_text(encoding='utf-8'))
        for repo, entry in state['models'].items():
            if entry.get('status') == 'downloaded' and not repo.startswith(('Tongyi-MAI/', 'Wan-AI/')):
                reference = ROOT / 'models' / ('models--' + repo.replace('/', '--')) / 'refs/main'
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_text(entry['revision'], encoding='utf-8')
        source = next((ROOT / 'input/phase1').rglob('*.mp4'))
        import imageio_ffmpeg
        wave_file = folder / 'speech-control.wav'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y', '-i', str(source),
                        '-t', '6', '-vn', '-ac', '1', '-ar', '16000', str(wave_file)], check=True)
        from hinglish_cut.media import read_audio
        audio = read_audio(wave_file, 0, 6)
        def speech():
            from hinglish_cut.backends import LocalSpeech
            from hinglish_cut.model import Settings
            engine = LocalSpeech(Settings(device='cuda', offline=True, cpu_threads=8), ROOT / 'models')
            try:
                assert not engine.detect(np.zeros(16000, np.float32))
                transcript = engine.recognize(audio)
                assert transcript.strip()
                words = engine.align(audio, transcript)
                assert words and all(0 <= word.start <= word.end <= 6.3 for word in words)
                return {'source': str(source), 'transcript': transcript, 'word_count': len(words), 'silence_vad': 'passed'}
            finally:
                engine.close()
        check('hinglish_speech_vad_and_alignment', speech)
        def turbo():
            from faster_whisper import WhisperModel
            manifest = json.loads((ROOT / 'models/meaning-upgrade.json').read_text(encoding='utf-8-sig'))
            model = WhisperModel(manifest['speech_path'], device='cuda', compute_type='float16', cpu_threads=8, local_files_only=True)
            segments, _ = model.transcribe(audio, language='hi', beam_size=3)
            transcript = ' '.join(row.text for row in segments)
            assert transcript.strip()
            del model
            gc.collect()
            return {'transcript': transcript}
        check('independent_turbo_speech', turbo)
        def semantic():
            from hinglish_niche.style_memory import StyleEmbedder
            embedder = StyleEmbedder(ROOT)
            vectors = embedder.encode(['cricket documentary bowling', 'video editing seekhna'])
            assert vectors.shape == (2, 384) and np.isfinite(vectors).all()
            return {'shape': list(vectors.shape), 'norms': np.linalg.norm(vectors, axis=1).tolist()}
        check('fixed_e5_retrieval_encoder', semantic)
        def clip():
            from hinglish_broll.vision import Vision
            model = Vision('openai/clip-vit-base-patch32', ROOT, device='cuda', threads=8)
            text = model.texts(['a red circle', 'a blue square'])
            images = model.images([Image.new('RGB', (224, 224), 'red')])
            assert text.shape == (2, 512) and images.shape == (1, 512)
            assert np.isfinite(text).all() and np.isfinite(images).all()
            return {'text_shape': list(text.shape), 'image_shape': list(images.shape)}
        check('clip_broll_ranking', clip)
        def clap():
            from hinglish_sound.listen import Listener
            model = Listener(ROOT, device='cuda', threads=8)
            text = model.texts(['a person talking'])
            tone = np.sin(np.arange(48000, dtype=np.float32) * (2 * np.pi * 440 / 48000)) * .1
            audio_vectors = model.audio([tone])
            assert text.shape == audio_vectors.shape and np.isfinite(audio_vectors).all()
            return {'shape': list(text.shape)}
        check('clap_audio_ranking', clap)
        def fallback():
            from hinglish_broll.llm import LocalLLM
            model = LocalLLM(ROOT, threads=8, context=4096)
            try:
                answer = model.json('Return a JSON object with ok set to true.', {'validation': str(uuid.uuid4())},
                                    {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}, max_tokens=64)
                assert answer.get('ok') is True
                result = {'answer': answer, 'backend': model.manifest.get('backend', 'llama.cpp'),
                          'model': model.manifest.get('ollama_model', model.manifest['judge_path'])}
                if result['backend'] == 'ollama':
                    result['residency'] = model.session.get('http://127.0.0.1:11434/api/ps', timeout=15).json()
                else:
                    result['gpu_layers'] = model.manifest.get('gpu_layers', 0)
                return result
            finally:
                model.close()
        check('bundled_qwen_structured_output', fallback)
        def faces():
            from hinglish_zoom.faces import FaceLocator
            locator = FaceLocator(ROOT)
            assert locator.yunet is not None
            assert locator._detect(Image.new('RGB', (320, 320), 'white')) is None
            return {'engine': 'YuNet', 'blank_image_inference': 'passed'}
        check('yunet_face_location', faces)
        def cutouts():
            os.environ['U2NET_HOME'] = str(ROOT / 'models/rembg')
            from rembg import new_session, remove
            result = []
            for name in ('birefnet-general-lite', 'isnet-general-use'):
                session = new_session(name, providers=['CPUExecutionProvider'])
                image = remove(Image.new('RGB', (128, 128), 'white'), session=session)
                assert image.mode == 'RGBA' and image.size == (128, 128)
                result.append({'model': name, 'output': image.mode})
                del session
                gc.collect()
            return result
        check('background_removal_onnx', cutouts)
        torch.cuda.empty_cache()
    print(json.dumps(checks, indent=2, ensure_ascii=False), flush=True)
    return 0 if all(row['passed'] for row in checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
