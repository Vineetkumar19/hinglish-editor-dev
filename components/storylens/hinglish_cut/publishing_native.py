"""Isolated exact-base PEFT inference for the explicitly selected publishing model."""
import json,os,subprocess,time,uuid
from pathlib import Path

def selected(policy,body):
    setting=policy.get('publishing_native_runtime',{})
    return bool(setting.get('enabled') and body.get('model')==setting.get('model'))

def post(root,body,policy,on_content=None):
    from requests import Response
    from .gpu_lock import gpu_lock,child_environment,_child_lease
    from .model_preferences import release_ollama
    root=Path(root);setting=policy['publishing_native_runtime']
    folder=root/'cache/app/publishing-native'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    payload={'body':body,'base':setting['base'],'adapter':setting['adapter']}
    (folder/'request.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    with gpu_lock(root):
        release_ollama(root)
        # An already borrowed worker retains the original signed ancestor lease.
        # It awaits this one child while holding its child slot, so the child
        # verifies that lease rather than recursively locking the same slot.
        if _child_lease(root):env=dict(os.environ)
        else:env=child_environment(root)
        env['STORYLENS_NATIVE_PARENT_PID']=str(os.getpid())
        payload['stream_reply']=callable(on_content)
        (folder/'request.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
        command=[setting['python'],'-E','-X','utf8',str(root/'tools/publishing_training/native_worker.py'),str(folder)]
        with (folder/'worker.log').open('w',encoding='utf8') as log:
            proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            position=0;content=''
            try:
                while proc.poll() is None:
                    events=folder/'text.jsonl'
                    if on_content and events.is_file():
                        with events.open(encoding='utf8') as stream:
                            stream.seek(position)
                            for line in stream:
                                content+=json.loads(line);on_content(content)
                            position=stream.tell()
                    time.sleep(.2)
            except BaseException:
                proc.terminate();proc.wait();raise
        path=folder/'response.json'
        if proc.returncode or not path.is_file():
            detail=(folder/'error.json')
            cause=json.loads(detail.read_text())['error'] if detail.is_file() else 'The isolated trained publishing worker exited. Keep its saved request and worker log.'
            raise RuntimeError(cause+' Saved details: '+str(folder))
        result=json.loads(path.read_text('utf8'))
        if on_content:on_content(result['message']['content'])
        response=Response();response.status_code=200
        response._content=json.dumps(result,ensure_ascii=False).encode('utf8')
        return response
