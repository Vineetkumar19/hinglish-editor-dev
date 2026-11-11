"""Reusable channel direction for a direct image idea, using the local planner."""
import hashlib
import json
import os
from pathlib import Path
from .plan import Moment, find_entities, script_lines, names_in, _names

KNOWLEDGE=Path(__file__).with_name('channel_knowledge.json')
ENVELOPE='STORYLENS_IMAGE_IDEA_V1\n'

def decode_request(text):
    """The existing job bridge can transport new image settings without restart.

    This is text-only metadata, never a command, filename or instruction source.
    The ordinary script path remains unchanged.
    """
    if not text.startswith(ENVELOPE):return text,{}
    try:
        body=json.loads(text[len(ENVELOPE):])
        if not isinstance(body,dict) or set(body)-{'idea','channel','purpose'}:raise ValueError()
        idea=body['idea']
        if not isinstance(idea,str) or not idea.strip() or len(idea)>6000:raise ValueError()
        if body.get('channel','auto') not in ('auto','general','gaming','cricket'):raise ValueError()
        if body.get('purpose','scene') not in ('scene','thumbnail','background'):raise ValueError()
        return idea,dict(request_mode='idea',channel=body.get('channel','auto'),purpose=body.get('purpose','scene'))
    except (ValueError,KeyError,TypeError):
        raise ValueError('This image request could not be read. Your idea is kept; reopen AI Images and try again.') from None

def channel_context(channel,idea):
    cfg=json.loads(KNOWLEDGE.read_text('utf-8'))
    if channel=='auto':
        text=idea.casefold()
        cricket=('cricket','batsman','bowler','wicket','stump','ipl','gully','क्रिकेट','बल्ले','विकेट')
        gaming=('gaming','gamer','game','clutch','rooftop','minecraft','valorant','bgmi','pubg','gta','गेम')
        channel='cricket' if any(w in text for w in cricket) else 'gaming' if any(w in text for w in gaming) else 'general'
    return dict(channel=channel,version=cfg['version'],shared=cfg['shared'],
                direction=cfg.get(channel,{}).get('direction',[]),
                examples=cfg.get(channel,{}).get('examples',[]),
                sha256=hashlib.sha256(KNOWLEDGE.read_bytes()).hexdigest())

def image_planning_context(root,system,data,schema,planner='local model'):
    """Share the same domain knowledge with the unified Thumbnail workspace.

    Scope by the image-concept schema; unrelated editing/planning is unchanged.
    Full creator_profile guidance remains in the original payload.
    """
    properties=(schema or {}).get('properties',{})
    if not isinstance(data,dict) or 'story' not in data or 'design' not in data or 'concepts' not in properties:return system,data
    knowledge=channel_context('auto',str(data['story']))
    if knowledge['channel']=='general' and data.get('profile') in ('gaming','cricket'):
        knowledge=channel_context(data['profile'],str(data['story']))
    payload={**data,'image_channel_knowledge':knowledge}
    system+='\nUse image_channel_knowledge for subject-specific gaming/cricket anatomy, equipment, setting and composition. Follow the requested category, style and headline setting. Preserve the supplied full creator profile and original story.'
    receipt=dict(planner=planner,original_idea=data['story'],design=data['design'],knowledge=knowledge,weight_training=False)
    context_file=os.environ.get('HINGLISH_CREATOR_CONTEXT_FILE')
    if context_file:
        folder=Path(context_file).resolve().parent
        allowed=(Path(root)/'cache/app/jobs').resolve()
        if folder.is_relative_to(allowed):
            (folder/'image-channel-guidance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
    return system,payload

def plan_idea(brain,idea,settings,progress=print):
    idea=idea.strip()
    if not idea:raise ValueError('Describe the image you want, then choose Generate images.')
    if len(idea)>6000:raise ValueError('Keep one image idea under 6,000 characters, or use Pictures from a script.')
    knowledge=channel_context(settings.channel,idea)
    entities=find_entities(brain,script_lines(idea),progress)
    schema={'type':'object','properties':{'prompt':{'type':'string'},'reason':{'type':'string'}},'required':['prompt','reason']}
    system='''You direct ONE image for a creator's gaming or cricket channel. This is a direct image request, not a script that you may skip. Preserve the user's precise scene, action, quantities, mood, viewpoint and exclusions. Write one concrete 45-110 word ENGLISH image prompt. Follow the supplied persistent channel guidance. Do not name real people, brands, teams, logos or copyrighted characters in the generated scene: use a descriptive generic stand-in for do_not_show names while retaining the requested context. Real places are allowed. Do not add a factual claim, scoreboard, watermark or a headline. The user's art style is applied separately. If purpose is thumbnail, leave useful space for a later headline/creator cutout; otherwise do not force a thumbnail composition. Return prompt and one short reason.'''
    answer=brain.json(system,{'idea':idea,'purpose':settings.purpose,'aspect':settings.aspect,
                             'channel_knowledge':knowledge,'do_not_show':entities['people']+entities['brands']},schema,max_tokens=900,think=False)
    prompt=' '.join(str(answer.get('prompt') or '').split())
    if not 20<=len(prompt.split())<=150:
        raise ValueError('The image direction was incomplete. Your idea is kept; try Generate images again.')
    if names_in(prompt,_names(entities)):
        raise ValueError('The image direction still contains a named person or brand. Your idea is kept; describe a generic character or athlete and try again.')
    receipt=dict(knowledge=knowledge,planner=brain.name,usage=getattr(brain,'last_usage',{}),
                 original_idea=idea,purpose=settings.purpose,prompt=prompt,reason=str(answer.get('reason') or ''),
                 weight_training=False)
    progress(f'Prepared your {knowledge["channel"]} image direction')
    return [Moment(0,0,5,idea,'image',prompt,why=str(answer.get('reason') or ''),importance=8)],entities,receipt
