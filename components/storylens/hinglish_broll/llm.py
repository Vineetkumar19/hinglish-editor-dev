"""Local quantized Qwen client: native llama.cpp or the imported Ollama model."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

import requests

from hinglish_clean.detection import write_json
from hinglish_semantic.setup_meaning import require


class LocalLLM:
    def __init__(self, root, threads=4, context=8192):
        self.root = Path(root)
        self.manifest = require(self.root)
        self.threads, self.context = threads, context
        self.process = self.session = self.log = None
        self.cache = self.root / 'cache' / 'broll' / 'llm'

    def start(self):
        if self.process is not None:
            return
        if self.manifest.get('backend') == 'ollama':
            if self.session is None:
                from hinglish_cut.ollama_runtime import start
                self.session, self.url = start(self.manifest)
            return
        if self.manifest.get('gpu_layers', 0):
            from hinglish_cut.model_preferences import release_ollama
            release_ollama(self.root)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        key = secrets.token_urlsafe(24)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log = (self.cache / f'runtime-{os.getpid()}.log').open('w', encoding='utf-8')
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers['Authorization'] = 'Bearer ' + key
        # Old manifests retain CPU mode; the validated CUDA runtime opts in.
        args = [self.manifest['server_path'], '-m', self.manifest['judge_path'], '--host', '127.0.0.1',
                '--port', str(port), '--api-key', key, '-t', str(self.threads), '-c', str(self.context),
                '-np', '1', '-ngl', str(int(self.manifest.get('gpu_layers', 0)))]
        try:
            self.process = subprocess.Popen(args, stdout=self.log, stderr=subprocess.STDOUT,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('The local AI model could not start; see ' + str(self.cache))
                try:
                    if self.session.get(self.url + '/health', timeout=2).status_code == 200:
                        return
                except requests.RequestException:
                    pass
                time.sleep(.25)
            raise TimeoutError('The local AI model did not become ready in 180 seconds')
        except BaseException:
            self.close()
            raise

    def json(self, system, data, schema, max_tokens=1200):
        """Ask for JSON matching `schema`; answers are cached by their exact inputs."""
        from hinglish_niche.profiles import inject
        system, data = inject(system, data, root=self.root)
        spec = {'v': 1, 'system': system, 'schema': schema, 'data': data,
                'model': self.manifest['judge_revision'], 'runtime': self.manifest.get('runtime_version')}
        if self.manifest.get('backend') == 'ollama':
            spec.update(backend='ollama', ollama_model=self.manifest['ollama_model'],
                        ollama_version=self.manifest.get('ollama_version'))
            if self.manifest.get('native_api'): spec['native_api']=True
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / (key + '.json')
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        request = {
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}],
            'temperature': 0, 'seed': 0, 'max_tokens': max_tokens,
            'response_format': {'type': 'json_object', 'schema': schema}}
        last_error = None
        for attempt in range(2):
            try:
                self.start()
                body = request
                if self.manifest.get('native_api'):
                    from hinglish_cut.model_preferences import release_ollama
                    release_ollama(self.root, keep=self.manifest['ollama_model'])
                    response=self.session.post(self.url+'/api/chat',json={
                        'model':self.manifest['ollama_model'],'messages':request['messages'],
                        'format':schema,'stream':False,'think':False,'keep_alive':'30s',
                        'options':{'temperature':0,'seed':0,'num_predict':max_tokens,
                                   'num_ctx':min(self.context,8192)}},timeout=1200)
                    response.raise_for_status()
                    answer=response.json()
                    if answer.get('done_reason')!='stop':
                        raise ValueError('The local AI answer was cut short')
                    result=json.loads(answer['message']['content'])
                    write_json(file,result)
                    return result
                if self.manifest.get('backend') == 'ollama':
                    from hinglish_cut.ollama_runtime import completion
                    body = completion(self.manifest, request)
                response = self.session.post(self.url + '/v1/chat/completions', json=body, timeout=1200)
                response.raise_for_status()
                choice = response.json()['choices'][0]
                if choice.get('finish_reason') != 'stop':
                    raise ValueError('The local AI answer was cut short')
                result = json.loads(choice['message']['content'])
                write_json(file, result)
                return result
            except requests.RequestException as error:
                last_error = error
                self.close()
                if attempt == 0:
                    time.sleep(3)
        raise RuntimeError('The bundled local AI stopped twice. Close other large apps and try again.') from last_error

    def close(self):
        if self.manifest.get('backend') == 'ollama':
            from hinglish_cut.ollama_runtime import close
            close(self.session, self.manifest)
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=10)
            self.process = None
        if self.session: self.session.close(); self.session = None
        if self.log: self.log.close(); self.log = None
