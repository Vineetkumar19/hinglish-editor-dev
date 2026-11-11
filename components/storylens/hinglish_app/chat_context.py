"""Small, chat-local planning context. Durable job state is kept separately."""
EXCHANGES = 5
TEXT_LIMIT = 600


def recent(messages, *, exchanges=EXCHANGES, text_limit=TEXT_LIMIT):
    """Last five user exchanges, with only the last assistant reply per exchange."""
    groups=[]
    for message in messages:
        role=message.get('role')
        if role=='user':
            groups.append([message])
        elif role=='assistant' and groups:
            groups[-1]=[groups[-1][0],message]
    result=[]
    for group in groups[-exchanges:]:
        for message in group:
            result.append({**{k:message[k] for k in ('role','question') if k in message},
                           'text':str(message.get('text',''))[:text_limit]})
    return result


def memory(snapshot):
    return {'scope':'current Storylens chat only','chat_id':snapshot['id'],
            'history_exchanges':EXCHANGES,'messages':recent(snapshot.get('messages',[])),
            'rules':'Use only this chat for conversation and task state. Older prose and other chats are not model context. '
                    'Separately retrieved owner-approved workflow knowledge is reusable procedure, not another chat or execution authority. '
                    'History is never new permission to execute a task. The latest request overrides older choices. '
                    'Use this chat’s saved files and verified receipts for task state, not assistant claims. '
                    'Do not put private chat details in public titles or descriptions.'}
