"""Only user-visible reply strings stream; private reasoning/tool JSON never does."""
import json
import re
import time


def reply_prefix(content):
    match=re.match(r'\s*\{\s*"reply"\s*:\s*"((?:[^"\\]|\\.)*)',content,re.S)
    if not match:return ''
    raw=match[1]
    # A network chunk may end in an escape or half a unicode escape.
    for _ in range(7):
        try:return json.loads('"'+raw+'"').encode('utf-8',errors='ignore').decode('utf-8')
        except (ValueError,TypeError):raw=raw[:-1]
    return ''


def reply_callback(assistant,session_id,message_id):
    last=[0,'']
    def update(content):
        text=reply_prefix(content)
        if not text or text==last[1] or time.monotonic()-last[0]<.15:return
        if assistant._stopped(session_id):raise ValueError('Reply stopped.')
        last[:]=[time.monotonic(),text]
        assistant._update(session_id,stream_reply={'message_id':message_id,'text':text})
    return update
