"""Let the configured local Qwen author native Hyperframes source, not shape presets."""
import argparse,hashlib,json,os,re,shutil
from pathlib import Path
from html.parser import HTMLParser

NAMES=('index.html','compositions/scene1.html','compositions/scene2.html','compositions/scene3.html')


class _Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def get(self,key,default=None):return self.attrs.get(key,default)
    def __getitem__(self,key):return self.attrs[key]
    def find_all(self,name=None,attrs=None,string=False):
        found=[]
        for child in self.children:
            if isinstance(child,str):
                if string:found.append(child)
                continue
            match=(name in (None,True) or child.tag==name or isinstance(name,list) and child.tag in name)
            match=match and all(k in child.attrs and (v is True or child.attrs[k]==v) for k,v in (attrs or {}).items())
            if match and not string:found.append(child)
            found.extend(child.find_all(name,attrs,string))
        return found
    def find(self,name=None,attrs=None):return next(iter(self.find_all(name,attrs)),None)


def parse_html(source):
    class Tree(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=True);self.root=_Node();self.stack=[self.root]
        def handle_starttag(self,tag,attrs):
            n=_Node(tag,attrs);self.stack[-1].children.append(n)
            if tag not in ('meta','link','img','br','hr','input','source','area','base','wbr','embed'):self.stack.append(n)
        def handle_startendtag(self,tag,attrs):self.stack[-1].children.append(_Node(tag,attrs))
        def handle_endtag(self,tag):
            for i in range(len(self.stack)-1,0,-1):
                if self.stack[i].tag==tag:self.stack=self.stack[:i];break
        def handle_data(self,data):self.stack[-1].children.append(data)
    parser=Tree();parser.feed(source);return parser.root


def checked_source(source):
    if not isinstance(source,str) or len(source)>90000:raise ValueError('Local Hyperframes source invalid: HTML source must be a bounded string.')
    forbidden=r'\b(?:fetch|XMLHttpRequest|WebSocket|Worker|eval|setTimeout|setInterval|requestAnimationFrame)\b|new\s+Function\b|Date\.now|Math\.random|document\.(?:cookie|write)|(?:localStorage|sessionStorage)|(?:window\.)?(?:parent|top)\.|\bnavigator\.'
    if re.search(forbidden,source):raise ValueError('Local Hyperframes source invalid: use deterministic GSAP only, without network, storage, timers or external window access.')
    soup=parse_html(source)
    if soup.find(['iframe','object','embed','form']):raise ValueError('Local Hyperframes source invalid: embedded browsing/forms are unavailable.')
    for tag in soup.find_all(True):
        for key,value in tag.attrs.items():
            if key.lower().startswith('on'):raise ValueError('Local Hyperframes source invalid: no inline event handlers.')
            if key in ('src','href','data-composition-src'):
                value=str(value)
                if not (value.startswith('assets/') or value in NAMES or value.startswith('#')):raise ValueError('Local Hyperframes source invalid: only supplied project-relative assets/compositions are available.')
    for value in re.findall(r'url\([\s\'"]*([^\)\'"\s]+)',source,re.I):
        if not value.startswith(('assets/','#')):raise ValueError('Local Hyperframes source invalid: CSS assets must be local.')
    return source


def validate_files(files):
    if set(files)!=set(NAMES):raise ValueError('Local Hyperframes source invalid: return exactly index.html and the three named scene files.')
    for source in files.values():checked_source(source)
    return files


def validate_project(files,script):
    validate_files(files);root=parse_html(files['index.html'])
    main=root.find(attrs={'data-composition-id':'main'})
    if not main or float(main.get('data-duration',0))!=16:raise ValueError('Local Hyperframes source invalid: root main must declare 16 seconds.')
    hosts=sorted(root.find_all(attrs={'data-composition-src':True}),key=lambda t:float(t.get('data-start',0)))
    if len(hosts)!=3:raise ValueError('Local Hyperframes source invalid: mount all three scenes once.')
    cursor=0.;captions=[]
    for i,host in enumerate(hosts,1):
        name=f'compositions/scene{i}.html';cid=f'scene{i}'
        if host['data-composition-src']!=name or host.get('id')!=cid or host.get('data-composition-id')!=cid or abs(float(host.get('data-start',0))-cursor)>.001:raise ValueError('Local Hyperframes source invalid: scene host IDs/files must match and cover the clock in order.')
        duration=float(host.get('data-duration',0));cursor+=duration
        if duration<3:raise ValueError('Local Hyperframes source invalid: allow at least 3 seconds per scene.')
        scene=parse_html(files[name]);template=scene.find('template')
        if not template or not template.find(attrs={'id':'root','data-composition-id':cid}):raise ValueError('Local Hyperframes source invalid: each scene needs its matching root INSIDE template.')
        if not re.search(r'window\.__timelines\s*\[\s*[\'"]'+cid+r'[\'"]\s*\]',files[name]):raise ValueError('Local Hyperframes source invalid: register the paused '+cid+' timeline.')
        for tag in scene.find_all(attrs={'data-script-caption':True}):captions.append(' '.join(str(t) for t in tag.find_all(string=True)).strip())
    if abs(cursor-16)>.001:raise ValueError('Local Hyperframes source invalid: scene durations must sum to 16 seconds.')
    if ' '.join(' '.join(captions).split())!=' '.join(script.split()):raise ValueError('Local Hyperframes source invalid: data-script-caption text must reproduce the exact statement once, across the three scenes.')
    return files


def bind_captions(files,chunks):
    """Exact input-text binding only; all model CSS, objects and tracks survive."""
    from html import escape
    if len(chunks)!=3:raise ValueError('Local Hyperframes source invalid: three caption chunks required for these three scene files.')
    result=dict(files)
    for i,chunk in enumerate(chunks,1):
        name=f'compositions/scene{i}.html'
        pattern=r'(<(?P<tag>p|div|span)\b[^>]*\bdata-script-caption(?:\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27))?[^>]*>).*?(</(?P=tag)\s*>)'
        def replace(match):
            opening=re.sub(r'\bdata-script-caption(?:\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27))?','data-script-caption',match[1])
            return opening+escape(chunk)+match[3]
        result[name],count=re.subn(pattern,replace,result[name],flags=re.I|re.S)
        if count!=1:raise ValueError('Local Hyperframes source invalid: exactly one existing caption element required in '+name)
    return result


def bind_font_assets(files):
    """Resolve the model's chosen Inter asset names; do not change its design."""
    result=dict(files)
    for name,source in result.items():
        for family,file in (('Inter-Regular','Inter-Regular.ttf'),('Inter-Bold','Inter-Bold.ttf')):
            if family in source and not re.search(r'@font-face\s*\{[^}]*font-family\s*:\s*[\'\"]?'+family,source,re.I):
                source=source.replace('<style>','<style>\n@font-face{font-family:"'+family+'";src:url("assets/fonts/'+file+'")}',1)
        result[name]=source
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--project',type=Path,required=True);parser.add_argument('--script',type=Path,required=True);parser.add_argument('--repair-from',type=Path);parser.add_argument('--use-reply',type=Path)
    args=parser.parse_args();root=args.root.resolve();project=args.project.resolve();script=args.script.read_text('utf-8').strip()
    if not project.is_relative_to(root/'output/motion'):raise ValueError('Use a new Motion Graphics project inside the workspace.')
    receipts=project/'local-qwen';receipts.mkdir(exist_ok=True)
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_visuals.brain import open_brain
    from hinglish_niche.profiles import Profiles,use
    from hinglish_motion.reference_composer import ask,save,obj,string
    guide=root/'tools/hyperframes-runtime/node_modules/hyperframes/dist/skills/hyperframes'
    core=(guide/'SKILL.md').read_text('utf-8');contract=core[core.index('## Contract'):core.index('## The HyperFrames desktop app')]
    format_=(guide/'references/format.md').read_text('utf-8');format_=format_[:format_.index('## Attributes')]
    explainer=(guide/'references/types/explainer.md').read_text('utf-8')
    profile=Profiles(root).context('general');save(receipts/'creator-context.json',profile)
    save(receipts/'request.json',{'exact_script':script,'model_only':True,'framework':'Hyperframes native HTML/CSS/GSAP','provided_guides':['hyperframes contract','composition format','explainer craft'],'reference_media':False})
    # Scope this fresh original film separately from the selected reference-copy
    # lesson. Full creator guidance and saved knowledge remain on disk.
    os.environ['STORYLENS_REFERENCE_FEATURE']='motion_original'
    files_schema=obj({n:string(30000) for n in NAMES});schema=obj({'title':string(100),'creative_intent':string(1200),'files':files_schema})
    system=('You are the SOLE LOCAL AI author of a native Hyperframes motion-graphics film. Write COMPLETE HTML/CSS/GSAP source; there are no shape presets or layout templates to fill. '
      'The user wants the exact normal statement visualized with interacting GRAPHIC ELEMENTS, not animated text cards, random moving rectangles or implementation labels. '
      'Choose your own coherent visual metaphor and visual narrative. Objects should visibly DO the things the words describe; aim for an understandable cause-and-effect sequence. '
      'Keep all original statement words once in supporting captions marked data-script-caption, split naturally at phrase boundaries. No narration. Do not present not achieved as success. '
      'Make a 16-second vertical 720x1280 film in three connected scenes, with purposeful independent element movement and a settled reading hold. Use declarative editable HTML/SVG objects with meaningful IDs. '
      'Read and follow the supplied OFFICIAL Hyperframes contract. Root main mounts scene1, scene2, scene3, each with the same host/scene/timeline ID. '
      'Files are exactly index.html, compositions/scene1.html, compositions/scene2.html, compositions/scene3.html. All scene content, style and JS go INSIDE template. '
      'Root loads assets/gsap.min.js. Provided font assets: assets/fonts/Inter-Regular.ttf and Inter-Bold.ttf. No external assets, fetch, imports, URLs, storage, timers or user events. '
      'Use gsap.timeline({paused:true}) and window.__timelines["main"/"scene1"/...]. No manual play/seek. Make each timeline reach its declared scene duration. '
      'Clip hosts have class clip, explicit numeric data-start and data-duration, data-track-kind graphics; total16seconds with no gaps. Animate children, never hide/toggle the timed clip itself. '
      'Use strong readable contrast, safe margins, clear large objects and varied purposeful motion. Labels name concepts, never text1, rect, moving-object or layer IDs. '
      'Return only the requested JSON with all FOUR complete source files, not excerpts. Do not implement shell commands or network operations.')
    data={'task':'Create the native Hyperframes film requested by the owner.','normal_statement':script,'official_contract':contract,'official_mount_example':format_,'explainer_craft':explainer,'canvas':{'width':720,'height':1280,'duration':16},'feedback':[]}
    if args.repair_from:
        previous=json.loads(args.repair_from.read_text('utf-8'))['answer']
        system=('You are the LOCAL Qwen author repairing your OWN native Hyperframes HTML/CSS/GSAP project. Return all four complete source files, retaining your visual metaphor and exact user statement. '
                'Choose every layout/animation correction yourself from the concrete checker feedback. Do not just hide errors with overlap exceptions. '
                'The statement is normal narrative content, not a software error. Its ending says reliability is NOT achieved; never show SUCCESS/FIXED/FILLED as the final outcome. '
                'Exact caption text is bound from the source into the caption elements; keep one data-script-caption element in each scene. '
                'Follow the provided native Hyperframes contract: correct template mounts, local asset paths, matching registered paused timelines, readable separate caption zones, independent graphic motion. '
                'No external URLs, network, storage, timers, user events, arbitrary commands or new dependencies. Only the schema JSON, with COMPLETE code, not a patch or excerpt.')
        data={'task':'Correct your OWN native Hyperframes code without replacing it with preset shapes. Keep your established visual metaphor; repair the specified defects.',
              'normal_statement':script,'current_files':previous['files'],
              'required_visible_caption_chunks':re.split(r'(?<=\.)\s+|(?<=,)\s+(?=but\b)',script),
              'feedback':json.loads((project/'local-qwen/feedback.json').read_text('utf-8')),
              'contract':'Root main and three scenes, total16s,720x1280. Matching host/child/timeline ids scene1/scene2/scene3. One paused timeline each; root initializes window.__timelines. All child markup/CSS/JS inside template; scene #root absolute inset0. Local assets only. Preserve each supplied caption chunk as ACTUAL child text inside <p data-script-caption>...</p>, not as an attribute value. Strong contrast; safe margins. Change objects through GSAP, not only text fades. No displayed success when the words say not achieved.'}
    prior=[int(p.stem.rsplit('-',1)[1]) for p in receipts.glob('author-*.json') if p.stem.rsplit('-',1)[1].isdigit()]
    base=max(prior,default=0)
    chunks=re.split(r'(?<=\.)\s+|(?<=,)\s+(?=but\b)',script)
    if args.use_reply:
        saved=json.loads(args.use_reply.read_text('utf-8'));answer=saved['answer'];model=saved['model'];raw_files=answer['files'];answer={**answer,'files':bind_font_assets(bind_captions(raw_files,chunks))};validate_project(answer['files'],script)
    else:
      print('Queued for the shared GPU; Local Qwen will author native Hyperframes source.',flush=True)
      with gpu_lock(root),use(profile):
        brain=open_brain(root,'auto',progress=lambda m:print(m,flush=True));brain.cache_enabled=False
        try:
            for attempt in range(2):
                print(f'Local Qwen writing native Hyperframes HTML/GSAP (attempt {attempt+1}).',flush=True)
                answer=ask(brain,receipts,f'author-{base+attempt+1}',system,data,schema,4000 if args.repair_from else 6500,think=True)
                raw_files=answer['files'];answer={**answer,'files':bind_font_assets(bind_captions(raw_files,chunks))}
                try:validate_project(answer['files'],script);break
                except ValueError as e:
                    print(str(e),flush=True);data['feedback']=[str(e)]
            else:raise ValueError('Local Qwen did not produce a complete native Hyperframes project after correction.')
        finally:brain.close()
        model=brain.name
    for name,source in answer['files'].items():
        file=project/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(source,'utf-8')
    assets=project/'assets';(assets/'fonts').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(root/'hinglish_motion/web/vendor/gsap.min.js',assets/'gsap.min.js')
    for name in ('Inter-Regular.ttf','Inter-Bold.ttf'):shutil.copyfile(root/'hinglish_motion/web/fonts'/name,assets/'fonts'/name)
    save(receipts/'authorship.json',{'model':model,'manual_creative_edits':False,'mechanical_caption_binding':True,'mechanical_font_asset_registration':True,'primitive_template_used':False,'exact_statement':script,'raw_files':{n:hashlib.sha256(s.encode('utf-8')).hexdigest() for n,s in raw_files.items()},'files':{n:hashlib.sha256(s.encode('utf-8')).hexdigest() for n,s in answer['files'].items()},'weights_updated':False})
    (project/'SPEC.md').write_text(answer['creative_intent']+'\n\nExact supplied statement:\n'+script,'utf-8')
    print('Local Qwen native project written: '+str(project),flush=True)


if __name__=='__main__':main()
