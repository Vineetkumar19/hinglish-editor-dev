"""Native Resolve Studio window. Standard-library client, non-destructive imports.
Requires Resolve Studio's Python scripting support and Fusion UIManager.
"""
from pathlib import Path
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
import webbrowser
import math

TOOLS=[('clean','Smart Clean'),('script','Script Edit'),('captions','Auto Captions'),('broll','B-roll'),
       ('visuals','Smart Visuals'),('zoom','Smart Zoom'),('sound','Sound Design'),('eyecontact','Eye Contact'),
       ('shorts','Long to Shorts'),('aiimage','AI Images'),('aivideo','AI Video'),('motion','Motion Graphics')]
TIMELINE={'broll','visuals','zoom','sound','eyecontact','aiimage','aivideo','motion'}


class Bridge:
    def __init__(self,config):
        self.config=config;self.root=Path(config['root']);self.url=config.get('bridge','http://127.0.0.1:8765');self.token=''
        if self.url!='http://127.0.0.1:8765':raise RuntimeError('Unexpected bridge address. Reinstall the editor runtime.')

    def connect(self):
        try:self.request('/api/health',authorized=False)
        except Exception:
            launch=self.config.get('launcher')
            command=[*launch,'--edition','plugins','--no-open'] if launch else [str(self.root/'.venv/Scripts/python.exe'),'-m','hinglish_app','--root',str(self.root),'--no-open']
            subprocess.Popen(command,cwd=self.config.get('engine_root',str(self.root)),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(40):
                time.sleep(.25)
                try:self.request('/api/health',authorized=False);break
                except Exception:continue
            else:raise RuntimeError('The local runtime did not start. Open Storylens once to finish setup.')
        self.token=json.loads((self.root/'cache/app/bridge.json').read_text(encoding='utf-8'))['token']

    def request(self,path,data=None,authorized=True):
        headers={'Content-Type':'application/json'}
        if authorized:headers['X-Hinglish-Token']=self.token
        request=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            try:message=json.load(error).get('error','Local editor request failed.')
            except ValueError:message='Local editor request failed.'
            raise RuntimeError(message) from error


def selected_media(project):
    selection=project.GetMediaPool().GetSelectedClips()
    clips=selection.values() if isinstance(selection,dict) else selection or []
    paths=[]
    for clip in clips:
        path=clip.GetClipProperty('File Path')
        if path and path not in paths:paths.append(path)
    return paths


def import_result(project,result):
    pool=project.GetMediaPool();names=[]
    for path in result.get('xml_files',[]):
        timeline=pool.ImportTimelineFromFile(path,{'timelineName':'Hinglish '+Path(path).stem})
        if not timeline:raise RuntimeError('Resolve could not import '+Path(path).name)
        names.append(timeline.GetName())
    if not names:
        paths=result.get('previews') or result.get('media',[])
        if not paths or not pool.ImportMedia(paths):raise RuntimeError('No importable result. Review and render the output first.')
        names.append('Generated media imported into Media Pool')
    return names


def beat_fps(timeline):
    rate = float(timeline.GetSetting('timelineFrameRate'))
    for nominal in (24, 30, 60, 120):
        if abs(rate - nominal * 1000 / 1001) < .01:
            return nominal * 1000 / 1001
    return rate


def beat_checkpoint(resolve, project, root, label):
    folder = Path(root) / 'output/beats/project-backups'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (str(time.time_ns()) + '-' + label + '.drp')
    if not resolve.GetProjectManager().ExportProject(project.GetName(), str(path)) or not path.is_file():
        raise RuntimeError('Resolve project checkpoint failed; no timeline changes were started.')
    return str(path)


def music_context(project, track_number=1, clip_number=1):
    timeline = project.GetCurrentTimeline()
    if not timeline: raise RuntimeError('Open a timeline with your music first.')
    clips = timeline.GetItemListInTrack('audio', track_number) or []
    if not 1 <= clip_number <= len(clips): raise RuntimeError('Choose a valid music audio track and clip number.')
    clip = clips[clip_number - 1]
    media = clip.GetMediaPoolItem()
    if not media: raise RuntimeError('The music must be a local media clip, not a compound clip.')
    fps = beat_fps(timeline)
    # Audio-only media uses timeline frame units for left offsets. Video-linked
    # audio may use source FPS; reject ambiguity rather than quietly drift.
    source_fps = media.GetClipProperty('FPS')
    source_fps = float(source_fps) if source_fps and float(source_fps)>0 else fps
    if abs(source_fps - fps) > .02 and clip.GetLeftOffset():
        raise RuntimeError('For trimmed linked audio with a different FPS, use a separate music file at timeline FPS.')
    start = clip.GetLeftOffset() / source_fps
    duration = clip.GetDuration() / fps
    # Newer Resolve versions expose source ranges. This also rejects retiming.
    source_start = getattr(clip, 'GetSourceStartFrame', None)
    source_end = getattr(clip, 'GetSourceEndFrame', None)
    if callable(source_start) and callable(source_end):
        first, last = source_start(), source_end()
        if isinstance(first, (int, float)) and isinstance(last, (int, float)):
            if abs((last - first + 1) / source_fps - duration) > 2 / fps:
                raise RuntimeError('Use normal-speed music for beat detection.')
    return {'path': media.GetClipProperty('File Path'), 'source_in': start,
            'source_out': start + duration, 'timeline_start': (clip.GetStart() - timeline.GetStartFrame()) / fps,
            'fps': fps, 'sequence_id': timeline.GetUniqueId()}


def beat_timeline(project, plan):
    timeline = project.GetCurrentTimeline()
    if not timeline or str(timeline.GetUniqueId()) != str(plan['sequence_id']):
        raise RuntimeError('The timeline changed. Detect the beats again.')
    if abs(beat_fps(timeline) - plan['fps']) > .001:
        raise RuntimeError('Timeline frame rate changed. Detect the beats again.')
    return timeline


def mark_music_beats(resolve, project, root, plan):
    timeline = beat_timeline(project, plan)
    beat_checkpoint(resolve, project, root, 'before-markers')
    old = timeline.GetMarkers() or {}
    for frame, marker in old.items():
        if str(marker.get('customData', '')).startswith('StorylensBeat:'):
            if not timeline.DeleteMarkerAtFrame(frame): raise RuntimeError('Could not replace an old Storylens marker.')
    occupied = set((timeline.GetMarkers() or {}).keys())
    added, skipped = 0, 0
    for index, beat in enumerate(plan['beats'], 1):
        # Timeline.AddMarker is relative to timeline start, even at 01:00:00:00.
        frame = beat['frame']
        if frame in occupied:
            skipped += 1
            continue
        if not timeline.AddMarker(frame, 'Cyan', 'Beat ' + str(index), 'Storylens ' + plan['density'], 1,
                                  'StorylensBeat:' + plan['id']):
            raise RuntimeError('Resolve could not add a beat marker. Earlier markers may already be present.')
        added += 1
    beat_checkpoint(resolve, project, root, 'after-markers')
    return f'{added} beat markers placed; {skipped} existing user marker positions preserved.'


def apply_music_effects(resolve, project, root, plan):
    original = beat_timeline(project, plan)
    if plan.get('video_track',1)>original.GetTrackCount('video'):
        raise RuntimeError('The selected video track does not exist.')
    beat_checkpoint(resolve, project, root, 'before-effects')
    timeline = original.DuplicateTimeline(original.GetName() + ' - Storylens beats')
    if not timeline or not project.SetCurrentTimeline(timeline):
        raise RuntimeError('Could not duplicate the timeline for effects.')
    offset, applied, skipped = timeline.GetStartFrame(), 0, 0
    for track in range(1, timeline.GetTrackCount('video') + 1):
        if track != plan.get('video_track', 1): continue
        if timeline.GetIsTrackLocked('video', track): continue
        for clip in timeline.GetItemListInTrack('video', track) or []:
            # Existing Fusion work is never rewired. A new graph lives only in the duplicate.
            if clip.GetFusionCompCount():
                skipped += 1
                continue
            keys, previous = {}, -1
            start, end = clip.GetStart() - offset, clip.GetEnd() - offset
            for beat in plan['beats']:
                frame = beat['frame']
                if not start <= frame < end: continue
                half = max(1, round(plan['duration'] * plan['fps'] / 2))
                left, right = max(start, frame - half), min(end - 1, frame + half)
                if left >= frame or frame >= right or left <= previous:
                    skipped += 1
                    continue
                for point, value in ((left, 1.), (frame, 1 + plan['amount'] / 100), (right, 1.)):
                    keys[point - start] = {1: value, 'Flags': {'Linear': plan['style'] == 'punch'}}
                previous = right
            if not keys: continue
            comp = clip.AddFusionComp()
            if not comp: raise RuntimeError('Resolve could not add a Fusion composition. A partial duplicate remains.')
            comp.Lock()
            try:
                inputs = comp.GetToolList(False, 'MediaIn') or {}
                outputs = comp.GetToolList(False, 'MediaOut') or {}
                if not inputs or not outputs: raise RuntimeError('Resolve did not create MediaIn/MediaOut nodes.')
                media_in, media_out = next(iter(inputs.values())), next(iter(outputs.values()))
                transform = comp.AddTool('Transform')
                transform.SetAttrs({'TOOLS_Name': 'StorylensBeatZoom'})
                transform.ConnectInput('Input', media_in)
                media_out.ConnectInput('Input', transform)
                base = comp.GetAttrs()['COMPN_RenderStart']
                spline = comp.BezierSpline()
                transform.Size = spline
                if spline.SetKeyFrames({base + frame: value for frame, value in keys.items()}) is False:
                    raise RuntimeError('Resolve rejected the zoom keyframes.')
                applied += len(keys) // 3
            finally:
                comp.Unlock()
    beat_checkpoint(resolve, project, root, 'after-effects')
    return f'{applied} zoom pulses applied; {skipped} existing Fusion clips/boundary events skipped. Original timeline preserved.'


def run_panel(resolve,fusion,bmd):
    project=resolve.GetProjectManager().GetCurrentProject()
    if not project:raise RuntimeError('Open a Resolve project first.')
    if not getattr(fusion,'UIManager',None):raise RuntimeError('This integration needs Resolve Studio with Fusion UIManager.')
    config=json.loads((Path(os.environ['LOCALAPPDATA'])/'Hinglish Editor/install.json').read_text(encoding='utf-8'))
    bridge=Bridge(config);bridge.connect();ui=fusion.UIManager;dispatcher=bmd.UIDispatcher(ui)
    window=dispatcher.AddWindow({'ID':'HinglishEditor','WindowTitle':'Storylens','Geometry':[180,60,460,850]},ui.VGroup([
        ui.Label({'Text':'Storylens · Local AI','Weight':0}),
        ui.HGroup([ui.Button({'ID':'CinematicOpen','Text':'Cinematic Reels'}),ui.Button({'ID':'CinematicImport','Text':'Import latest cinematic reel'})]),
        ui.Label({'Text':'Select media for cuts; use the open timeline for finishing.','Weight':0,'WordWrap':True}),
        ui.ComboBox({'ID':'Tool','Weight':0}),ui.ComboBox({'ID':'Typography','Weight':0}),
        ui.Label({'Text':'Beat Studio · music track / clip number','Weight':0}),
        ui.CheckBox({'ID':'BeatAuto','Text':'Auto-detect when this music track / clip changes','Checked':False,'Weight':0}),
        ui.HGroup([ui.SpinBox({'ID':'MusicTrack','Minimum':1,'Maximum':99,'Value':1}),ui.SpinBox({'ID':'MusicClip','Minimum':1,'Maximum':999,'Value':1})]),
        ui.HGroup([ui.ComboBox({'ID':'BeatDensity'}),ui.SpinBox({'ID':'BeatCount','Minimum':0,'Maximum':10000,'Value':0})]),
        ui.Label({'Text':'Maximum markers: 0 = density default. Use normal-speed music.','Weight':0}),
        ui.HGroup([ui.ComboBox({'ID':'BeatStyle'}),ui.SpinBox({'ID':'BeatAmount','Minimum':1,'Maximum':20,'Value':8})]),
        ui.Label({'Text':'Effects target video track · default V1','Weight':0}),ui.SpinBox({'ID':'BeatVideoTrack','Minimum':1,'Maximum':99,'Value':1}),
        ui.HGroup([ui.Button({'ID':'BeatDetect','Text':'1. Detect & mark beats'}),ui.Button({'ID':'BeatApply','Text':'2. Apply effects to beats','Enabled':False})]),
        ui.TextEdit({'ID':'Script','PlaceholderText':'Optional script; required for Script Edit.'}),
        ui.HGroup([ui.Button({'ID':'Run','Text':'Start edit'}),ui.Button({'ID':'Activate','Text':'Activate / settings'})]),
        ui.Button({'ID':'Support','Text':'Email support · vineetkd418@gmail.com','Weight':0}),
        ui.Label({'ID':'Status','Text':'Connected. Originals are preserved.','WordWrap':True,'Weight':0}),
        ui.HGroup([ui.Button({'ID':'Refresh','Text':'Refresh progress'}),ui.Button({'ID':'Review','Text':'Review output','Enabled':False}),ui.Button({'ID':'Import','Text':'Import new result','Enabled':False})])]))
    items=window.GetItems()
    for _,label in TOOLS:items['Tool'].AddItem(label)
    for number in range(1,6):items['Typography'].AddItem('Typography '+str(number))
    for label in ('Light · fewer', 'Medium · balanced', 'Strong · more'):items['BeatDensity'].AddItem(label)
    items['BeatDensity'].CurrentIndex=1
    for label in ('Punch zoom','Smooth zoom'):items['BeatStyle'].AddItem(label)
    current={'job':None,'result':None}
    def import_cinematic(event):
        try:
            job=bridge.request('/api/cinematic/import-manifest',{'host':'resolve'})
            beat_checkpoint(resolve,project,bridge.root,'before-cinematic-import')
            names=import_result(project,job['result'])
            beat_checkpoint(resolve,project,bridge.root,'after-cinematic-import')
            items['Status'].Text='Imported cinematic reel: '+', '.join(names)
        except Exception as error:items['Status'].Text=str(error)
    window.On.CinematicOpen.Clicked=lambda event:webbrowser.open(bridge.url+'/cinematic.html?host=resolve')
    window.On.CinematicImport.Clicked=import_cinematic
    beat_state={'job':None,'plan':None,'context':None,'last_auto':None}

    def detect_beats(event):
        try:
            if 'beat_markers_v1' not in bridge.request('/api/health').get('capabilities',[]):
                raise RuntimeError('Restart the local Storylens editor to enable Beat Studio.')
            context=music_context(project,items['MusicTrack'].Value,items['MusicClip'].Value)
            beat_state['context']=context;beat_state['plan']=None;items['BeatApply'].Enabled=False
            payload={**context,'host':'resolve','density':('light','medium','strong')[items['BeatDensity'].CurrentIndex]}
            if items['BeatCount'].Value:payload['target_count']=items['BeatCount'].Value
            beat_state['job']=bridge.request('/api/beats/analyze',payload)['id']
            items['BeatDetect'].Enabled=False;items['Status'].Text='Listening locally. Use Refresh progress if automatic refresh is unavailable.'
        except Exception as error:items['Status'].Text=str(error)

    def poll_beats():
        if items['BeatAuto'].Checked and not beat_state['job']:
            try:
                context=music_context(project,items['MusicTrack'].Value,items['MusicClip'].Value)
                if context!=beat_state['last_auto']:
                    beat_state['last_auto']=context;detect_beats(None)
            except Exception:pass
        if not beat_state['job']:return
        try:
            job=bridge.request('/api/beats/jobs/'+beat_state['job'])
            if job['status'] in ('queued','running'):return
            beat_state['job']=None;items['BeatDetect'].Enabled=True
            if job['status']!='complete':raise RuntimeError(job.get('error','Beat analysis failed.'))
            context=music_context(project,items['MusicTrack'].Value,items['MusicClip'].Value)
            if context!=beat_state['context']:raise RuntimeError('Music placement changed. Detect the beats again.')
            if not job['plan']['beats']:raise RuntimeError('No clear beats found; no markers added.')
            items['Status'].Text=mark_music_beats(resolve,project,bridge.root,job['plan'])
            beat_state['plan']=job['plan'];items['BeatApply'].Enabled=True
        except Exception as error:
            beat_state['job']=None;items['BeatDetect'].Enabled=True;items['Status'].Text=str(error)

    def apply_beats(event):
        try:
            if not beat_state['plan']:raise RuntimeError('Detect the music beats first.')
            if music_context(project,items['MusicTrack'].Value,items['MusicClip'].Value)!=beat_state['context']:
                raise RuntimeError('Music placement changed. Detect the beats again.')
            plan=bridge.request('/api/beats/effects',{'id':beat_state['plan']['id'],'host':'resolve',
                'style':('punch','smooth')[items['BeatStyle'].CurrentIndex],'amount':items['BeatAmount'].Value,'video_track':items['BeatVideoTrack'].Value})
            items['Status'].Text=apply_music_effects(resolve,project,bridge.root,plan)
            items['BeatApply'].Enabled=False
        except Exception as error:items['Status'].Text=str(error)

    def run(event):
        try:
            mode=TOOLS[items['Tool'].CurrentIndex][0]
            payload={'mode':mode,'host':'resolve','profile':'general','script':items['Script'].PlainText,
                     'caption_style':'typography_'+str(items['Typography'].CurrentIndex+1),'preview':True,'device':'cpu'}
            if mode in TIMELINE:
                timeline=project.GetCurrentTimeline()
                if timeline:
                    folder=bridge.root/'cache/app/exports';folder.mkdir(parents=True,exist_ok=True)
                    target=folder/('resolve-'+str(time.time_ns())+'.xml')
                    if not timeline.Export(str(target),resolve.EXPORT_FCP_7_XML,resolve.EXPORT_NONE):raise RuntimeError('Timeline export failed.')
                    payload['timeline_xml']=str(target)
                elif mode not in ('aiimage','aivideo','motion'):raise RuntimeError('Open the timeline you want to edit first.')
            else:
                paths=selected_media(project)
                if not paths:raise RuntimeError('Select video clips in the Media Pool first.')
                payload['source_paths']=paths
            current['job']=bridge.request('/api/jobs',payload)['id'];current['result']=None
            items['Run'].Enabled=False;items['Import'].Enabled=False;items['Review'].Enabled=False;items['Status'].Text='Edit queued. Processing on this computer.'
        except Exception as error:items['Status'].Text=str(error)

    def poll(event):
        poll_beats()
        if not current['job']:return
        try:
            job=bridge.request('/api/jobs/'+current['job']);items['Status'].Text=str(job['progress'])+'% · '+job['stage']
            if job['status'] in ('complete','failed'):
                current['job']=None;items['Run'].Enabled=True
                if job['status']=='complete':current['result']=job['result'];items['Review'].Enabled=True;items['Import'].Enabled=True
        except Exception as error:items['Status'].Text=str(error);items['Run'].Enabled=True;current['job']=None

    def import_now(event):
        try:items['Status'].Text='Imported: '+', '.join(import_result(project,current['result']))
        except Exception as error:items['Status'].Text=str(error)

    window.On.Run.Clicked=run;window.On.Import.Clicked=import_now
    window.On.BeatDetect.Clicked=detect_beats;window.On.BeatApply.Clicked=apply_beats
    window.On.Refresh.Clicked=poll
    window.On.Review.Clicked=lambda event:webbrowser.open(Path(current['result']['page']).as_uri())
    window.On.Activate.Clicked=lambda event:webbrowser.open(bridge.url+'/activation.html?edition=plugins')
    window.On.Support.Clicked=lambda event:webbrowser.open('mailto:vineetkd418@gmail.com?subject=Hinglish%20Editor%20support')
    window.On.HinglishEditor.Close=lambda event:dispatcher.ExitLoop()
    # Timer support differs across installed Fusion builds. Keep the integration
    # usable when absent rather than calling a nonexistent API and crashing.
    timer=None
    if callable(getattr(dispatcher,'AddTimer',None)):
        timer=dispatcher.AddTimer({'ID':'Poll','Interval':1000});timer.On.Timeout=poll
    window.Show()
    if timer:timer.Start()
    try:dispatcher.RunLoop()
    finally:
        if timer:timer.Stop()
        window.Hide()


if __name__=='__main__':run_panel(resolve,fusion,bmd)
