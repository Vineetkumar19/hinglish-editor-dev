"""Build an auditable knowledge-SFT corpus, never a claim of heard sound quality."""
from pathlib import Path
import hashlib
import json
import math
import re

SYSTEM=('You are Storylens\'s sound-design assistant for cricket documentaries and cinematic travel. '
        'Use the supplied evidence, preserve requested voice/music, and give relevant concise decisions. '
        'Distinguish physical sounds, ambience and editorial effects. Never invent observations, '
        'asset paths, completed tool actions or listening approval. /no_think')

REFERENCE_ONLY={1:'Document cover and operational status, not sound-design behaviour.',
                2:'Reader navigation.',
                32:'Dataset curation documentation retained as reference, not a live sound-planner target.',
                33:'Training procedure retained as reference, not audio-selection behaviour.',
                36:'Historical software audit, not current model knowledge.',
                37:'Rollout status, not current application capabilities.',
                40:'Sources and project evidence register.'}

def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def load_seeds(root):
    path=Path(root)/'output/pdf/sound-design-teaching-guide/teacher-seed-examples.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Time must be finite numeric, not boolean')
    return value

def validate_seed(row):
    inp=json.loads(row['prompt']);out=json.loads(row['chosen'])
    duration=number(inp['duration_s'])
    if duration<=0:raise ValueError('Invalid timeline')
    assets={x['asset_id']:x for x in inp['candidates']}
    if len(assets)!=len(inp['candidates']):raise ValueError('Duplicate asset ID')
    for cue in out['cues']:
        if cue['asset_id'] not in assets:raise ValueError('Unknown source')
        start=number(cue['timeline_start_s']);length=number(cue['duration_s']);source=number(cue['source_in_s'])
        if start<0 or source<0 or length<=0:raise ValueError('Invalid interval')
        if start+length>duration+1e-6:raise ValueError('Timeline overrun')
        if source+length>number(assets[cue['asset_id']]['duration_s'])+1e-6:raise ValueError('Source overrun')
        contact=cue.get('contact_target_s')
        if contact is not None and not start<=number(contact)<=start+length:raise ValueError('Contact outside cue')
    return inp,out

def build_corpus(root):
    source=Path(root)/'output/pdf/sound-design-teaching-guide/guide-content.json'
    pages=json.loads(source.read_text(encoding='utf-8'))
    rows=[];coverage=[]
    def add(page,title,question,answer,kind='guide_knowledge'):
        question=question.strip();answer=answer.strip()
        answer=re.sub(r'\s*\[(?:S|P)\d+\]','',answer)
        rid=digest(str(page)+'\n'+question+'\n'+answer)[:20]
        rows.append(dict(id=rid,source_page=page,source_title=title,source_kind=kind,
                         audio_quality_verified=False,messages=[{'role':'system','content':SYSTEM},
                         {'role':'user','content':question},{'role':'assistant','content':answer}]))
    for n,pg in enumerate(pages,1):
        if n in REFERENCE_ONLY:
            coverage.append(dict(page=n,title=pg['title'],status='reference_only',reason=REFERENCE_ONLY[n]));continue
        before=len(rows);heading='Core principle';group=[]
        def flush():
            if not group:return
            # Keep related paragraphs together; avoid artificial duplicated paraphrases.
            add(n,pg['title'],f'For {pg["title"].lower()}, explain {heading.lower()} and how to apply it.', '\n\n'.join(group))
            group.clear()
        for bi,block in enumerate(pg['blocks']):
            typ=block[0]
            if typ=='h':flush();heading=block[1]
            elif typ in ('p','b','call'):
                text=block[1]
                # Don't bake transient inventory counts or this document's operational status into weights.
                if n==5 and text.startswith('Our latest collection inventory'):continue
                if any(s in text for s in ['This document does not execute','This deliverable prepares','The companion seed examples','This is a proposed teaching representation']):continue
                group.append(text)
            elif typ=='table':
                flush();headers=block[1]
                for j,row in enumerate(block[2]):
                    answer='\n'.join(str(k)+': '+str(v) for k,v in zip(headers,row))
                    add(n,pg['title'],f'In {pg["title"].lower()}, what should I know about "{row[0]}"?',answer)
            elif typ=='code':
                flush();add(n,pg['title'],'Give a clearly labelled proposed intermediate example for a physical landing. Do not claim it is a live API or selected real file.',
                           'Proposed intermediate representation, not a current API contract. Retrieval has not selected an asset:\n'+block[1])
        flush()
        coverage.append(dict(page=n,title=pg['title'],status='included',examples=len(rows)-before,
                             note='Transient counts/status excluded; complete original page retained in reference source.'))
    for seed in load_seeds(root):
        inp,out=validate_seed(seed)
        task=('This is an illustrative fictional scenario and fictional candidate inventory, not inspected real media. '
              'Return a concept plan using only these IDs, with correct source/timeline bounds and no listening claims. '
              'It is not the production application schema.\n'+json.dumps(inp,ensure_ascii=False))
        add(31,'Teacher synthetic scenarios',task,json.dumps(out,ensure_ascii=False),'synthetic_concept')
    policy=Path(__file__).with_name('provider_lessons.json')
    for item in json.loads(policy.read_text(encoding='utf-8')):
        add(0,'Online sound retrieval policy',item['question'],item['answer'],'online_retrieval_policy')
    return rows,coverage

HOLDOUT=[
 ('train_passing','Travel clip: a train crosses left-to-right at 3-6 seconds while the narrator talks. The original rail sound is weak. What sources, duration and mixing priorities would you choose?',
  'Use a sustained matching rail/vehicle pass-by over the observed travel, perspective-appropriate environment, and any justified wheel/track detail. Keep narration intelligible, avoid arbitrary clicks and do not invent horn use.','physical source, sustained duration, speech priority'),
 ('cricket_pad','A cricket ball visibly strikes the batter\'s pad, not the bat. Narration describes a disputed LBW decision. What should the sound plan avoid?',
  'Avoid a clean bat crack, invented appeal or crowd verdict that changes the factual reading. Retain original audio if useful; use a padded contact only when justified, synchronized to the impact and labelled reconstructed if added.','correct material, documentary truth'),
 ('night_street','At midnight I show an empty city street. I say "yahaan nightlife kamaal hai" sarcastically. What ambience and accent fit?',
  'Use the established quiet street world at believable distance, protect the sarcastic delivery and consider a pause or one restrained comic response. Do not add party crowds, woodland birds or a loud traffic bed solely from the word nightlife.','context over keyword, restraint'),
 ('existing_engine','The source audio already has a convincing motorcycle engine and the owner-approved song. What should enhancement do?',
  'Preserve the source once. Listen for missing road or contact detail, supplement only useful gaps and avoid duplicating the engine or music. Do not claim independent song ducking if voice/music share a single mix.','preserve source, no duplication'),
 ('dry_slide','A child slides down a visibly dry indoor plastic slide. Available options: water splash, plastic friction, UI notification. Which is relevant?',
  'Plastic friction matched to observed movement and indoor perspective is relevant. Do not add water just because it is a slide. A UI notification does not replace the physical sound; keep any editorial accent separately motivated.','source relevance, material'),
 ('uncertain_contact','A shoe is visible in two frames 0.5 seconds apart, but touchdown is hidden. Can you provide an exact footstep timestamp?',
  'No exact contact can be established from those observations. Retain uncertainty and inspect finer frames or original audio if available; otherwise use a conservative inferred treatment or omit the precise accent.','uncertainty, no fake precision'),
 ('natural_sustain','A cyclist coasts on gravel for 2.8 seconds. The library has a 5-second gravel travel recording. Must the effect be trimmed to 0.2 seconds?',
  'No. Use a suitable sustained window for the observed movement, align its audible start, retain a natural ending and mix around speech. Avoid replacing the motion with repeated transient clicks.','duration follows action'),
 ('required_missing','The model proposes river ambience, but validation drops that layer for an invalid role. Only two title pops remain. What status should the system report?',
  'Report missing required river coverage and the role error; attempt a bounded structured repair or return a partial review state. Two surviving title pops are not a completed river sound design.','coverage, honest status'),
 ('offset_arithmetic','An event starts at 7.5 s. Its layer offset is -0.2 s. The source window has 0.3 s before its meaningful impact. When does the audible impact happen?',
  'The source window begins at 7.3 s, so the audible impact is at 7.6 s. If contact must be at 7.5 s, start the window at 7.2 s, corresponding to offset -0.3 s, subject to the supported role and bounds.','arithmetic, audible onset'),
 ('silent_emotion','A cricketer pauses silently after describing a loss; there is usable quiet room sound. Should five SFX layers fill that pause?',
  'No. Preserve the performance and room, allowing the pause to carry emotion. Five roles are options for an appropriate action, not a quota; an unnecessary comic sting or pile of impacts would undermine the scene.','intentional silence, emotional relevance'),
 ('library_novelty','A relevant engine was used earlier. The unused library alternative is horse galloping. Should novelty win?',
  'No. Source relevance outranks novelty. Reuse the matching engine when it supports continuity, find a valid alternative engine excerpt if useful, or report the gap. Do not substitute a different physical source to avoid repetition.','relevance over novelty'),
 ('clip_level','One source is a very loud impact and another is quiet rain. Both have a gain of -12 dB. Are they equally loud and acceptable?',
  'No. Clip gain is relative to different source levels. Measure and audition the excerpts in the mix, protect speech and preserve roles, headroom and useful attacks/decays. Equal gain is not equal perceived loudness.','relative gain, listen in context'),
]

def write(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rows,coverage=build_corpus(root)
    # All guide rules can be taught; holdout consists of separately authored application problems.
    def jsonl(name,data):(out/name).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data),encoding='utf-8')
    jsonl('train.jsonl',rows)
    holdout=[dict(id=i,source_kind='unseen_authored_application',messages=[{'role':'system','content':SYSTEM},
             {'role':'user','content':q},{'role':'assistant','content':a}],rubric=r,audio_quality_verified=False)
             for i,q,a,r in HOLDOUT]
    jsonl('holdout.jsonl',holdout)
    (out/'coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    summary=dict(training_examples=len(rows),heldout_application_questions=len(holdout),source_pages=40,
                 source_sha256=hashlib.sha256((root/'output/pdf/sound-design-teaching-guide/guide-content.json').read_bytes()).hexdigest(),
                 method='Knowledge/decision SFT pilot, not perceptual audio training or a production-quality claim',
                 model='Qwen3-14B',quantization='NF4 training base; original Q4_K_M serving model preserved',
                 train_sha256=hashlib.sha256((out/'train.jsonl').read_bytes()).hexdigest())
    (out/'dataset-receipt.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    write(root,root/'output/sound-training/20261030-qwen3-14b/dataset')
