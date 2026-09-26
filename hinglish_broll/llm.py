"""Small client for the local quantized Qwen model (llama.cpp server). No cloud inference."""
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
    def __init__(self, root, threads=4, context=16384):
        self.root = Path(root)
        self.manifest = require(self.root)
        self.threads, self.context = threads, context
        self.process = self.session = self.log = None
        self.cache = self.root / 'cache' / 'broll' / 'llm'

    def start(self):
        if self.process is not None:
            return
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
        # -ngl: the bundled llama.cpp build is CPU-only; a CUDA build can raise this later.
        args = [self.manifest['server_path'], '-m', self.manifest['judge_path'], '--host', '127.0.0.1',
                '--port', str(port), '--api-key', key, '-t', str(self.threads), '-c', str(self.context),
                '-np', '1', '-ngl', '0']
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
        spec = {'v': 1, 'system': system, 'schema': schema, 'data': data,
                'model': self.manifest['judge_revision'], 'runtime': self.manifest.get('runtime_version')}
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / (key + '.json')
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        self.start()
        response = self.session.post(self.url + '/v1/chat/completions', json={
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}],
            'temperature': 0, 'seed': 0, 'max_tokens': max_tokens,
            'response_format': {'type': 'json_object', 'schema': schema}}, timeout=1200)
        response.raise_for_status()
        choice = response.json()['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('The local AI answer was cut short')
        result = json.loads(choice['message']['content'])
        write_json(file, result)
        return result

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=10)
            self.process = None
        if self.session: self.session.close(); self.session = None
        if self.log: self.log.close(); self.log = None
