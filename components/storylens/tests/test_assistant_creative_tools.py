"""Injected CPU controller boundaries; no actual LLM, service worker or render."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hinglish_app.assistant_creative_tools import (
    requested, source_catalog, plan_request, execute, followup,
)
from hinglish_app.assistant_plan import validate_plan, schema, quick_plan, plan


BEAT_ID='a'*32
CINE_ID='b'*32


def prepared(tool='cinematic',**options):
    return dict(reply='Use the supplied sources.',question='',combine=False,
                steps=[dict(tool=tool,options=dict(music_source_id='song',
                    **({'shot_source_ids':['clip1','clip2'],'max_shots':2} if tool=='cinematic' else {}),**options))],
                creative_provenance={'provider':'injected-boundary','model':'synthetic','intervention':True})


class BoundaryBrain:
    name='Injected CPU fixture'
    def __init__(self,answers):self.answers=list(answers);self.calls=[];self.closed=False
    def json(self,system,data,schema,**kwargs):
        self.calls.append((system,copy.deepcopy(data),copy.deepcopy(schema),kwargs))
        return self.answers.pop(0)
    def close(self):self.closed=True


class BoundaryService:
    def __init__(self,job_id,result):self.id=job_id;self.result=result;self.starts=[];self.cancels=[];self.polls=0;self.states=['complete']
    def start(self,payload,**kwargs):self.starts.append((copy.deepcopy(payload),kwargs));return {'id':self.id,'status':'queued'}
    def snapshot(self,job_id):
        if job_id!=self.id:raise ValueError('Unknown fixture job')
        state=self.states[min(self.polls,len(self.states)-1)];self.polls+=1
        if state=='missing':raise ValueError('Fixture service restarted')
        return {'id':self.id,'status':state,'stage':'Fixture state','plan':self.result,'result':self.result}
    def cancel(self,job_id):self.cancels.append(job_id);return {'ok':True}


class BoundaryAssistant:
    def __init__(self,root,selected):
        self.root=root;self.data={'id':'chat1','profile':'gaming','attachments':selected,'messages':[],
                                  'active_request_message_id':'request1','last_paths':[],'steps':[],
                                  'stop':False,'status':'idle','pending':None}
        self.lock=threading.RLock()
        self.messages=[];self.stopped=False
        beat_folder=root/'output'/'beats'/BEAT_ID;beat_folder.mkdir(parents=True)
        beat=dict(id=BEAT_ID,path=selected[0]['path'],source_in=0,source_out=5,duration=5,
                  beats=[dict(frame=30,timeline_seconds=1,source_seconds=1,strength=.8)])
        (beat_folder/'beat-plan.json').write_text(json.dumps(beat),'utf-8')
        cine_folder=root/'output'/'cinematic-reels'/CINE_ID;cine_folder.mkdir(parents=True)
        video=cine_folder/'CINEMATIC_REEL.mp4';video.write_bytes(b'synthetic fixture, not rendered video')
        xml=cine_folder/'CINEMATIC_REEL.xml';xml.write_text('<synthetic/>','utf-8')
        cine=dict(folder=str(cine_folder),preview=str(video),xml_files=[str(xml)],shot_count=2,duration=5,
                  plan={'selection_method':'Local measured visual ranking, not semantic LLM judgement'})
        self.state=SimpleNamespace(beats=BoundaryService(BEAT_ID,beat),
                                   cinematic=BoundaryService(CINE_ID,cine),license_for=lambda _:None,
                                   work_lock=threading.RLock(),local_browser=SimpleNamespace(snapshot=lambda:{}),
                                   create_job=lambda *_:(_ for _ in ()).throw(AssertionError('No generic server worker')))
    def snapshot(self,_):return copy.deepcopy(self.data)
    def _update(self,_,**values):self.data.update(copy.deepcopy(values))
    def _message(self,_,role,text,**values):self.messages.append(dict(role=role,text=text,**values))
    def _stopped(self,_):return self.stopped
    def _get(self,_):return self.data
    def _progress(self,_,message):self.data['stage']=message
    def _update_user_message(self,*args,**kwargs):pass
    def context_memory(self,*args):return {'creator_profile':{'feedback':'preserve the complete creator guide'}}


class CreativeControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.selected=[]
        for id,name in [('song','song.mp3'),('clip1','one.mp4'),('clip2','two.mov')]:
            path=self.root/name;path.write_bytes(b'synthetic input only')
            self.selected.append(dict(id=id,name=name,path=str(path),kind='file'))
        self.assistant=BoundaryAssistant(self.root,self.selected)

    def run_creative(self,parsed=None,**kwargs):
        return execute(self.assistant,'chat1',parsed or prepared(),self.selected,'gaming',lambda _:None,
                       pause=lambda _:None,**kwargs)

    def test_catalog_uses_actual_ids_roles_not_paths_or_voice_recordings(self):
        cards=source_catalog(self.selected+[dict(id='voice',name='voice.wav',kind='voice',path='unread')])
        self.assertEqual(['song','clip1','clip2'],[c['id'] for c in cards])
        self.assertEqual(['music','clip_or_music','clip_or_music'],[c['role'] for c in cards])
        self.assertTrue(all('path' not in c for c in cards))

    def test_new_requests_always_reach_local_planner_not_quick_shortcut(self):
        self.assertTrue(requested('Make a cinematic reel with my song and clips'))
        self.assertIsNone(quick_plan('Make a cinematic reel with this music'))
        self.assertFalse(requested('Make cinematic motion graphics about a city'))
        brain=BoundaryBrain([prepared()])
        with patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch('hinglish_cut.gpu_lock.gpu_lock',return_value=nullcontext()):
            result,name=plan(self.root,'Make a cinematic reel',[],source_catalog(self.selected),False,
                             progress=lambda _:None,memory_context={'creator_profile':{'preserve':'full guidance'}})
        self.assertEqual('cinematic',result['steps'][0]['tool'])
        self.assertEqual('full guidance',brain.calls[0][1]['shared_memory']['creator_profile']['preserve'])
        self.assertEqual('injected-boundary',result['creative_provenance']['provider'])
        self.assertTrue(brain.closed)

    def test_normal_assistant_response_dispatches_selected_audio_ids_to_bridge(self):
        from hinglish_app.assistant import Assistant
        from hinglish_niche.profiles import CURRENT
        brain=BoundaryBrain([prepared()]);seen=[]
        original=brain.json
        def ask(*args,**kwargs):seen.append(copy.deepcopy(CURRENT.get()));return original(*args,**kwargs)
        brain.json=ask
        with patch('hinglish_niche.profiles.Profiles.context',return_value={'profile':'gaming','feedback':'full creator guide'}), \
             patch('hinglish_visuals.brain.open_brain',return_value=brain), \
             patch('hinglish_cut.gpu_lock.gpu_lock',return_value=nullcontext()), \
             patch('hinglish_app.workflow_memory.configuration',return_value={'enabled':False}), \
             patch('socket.socket',side_effect=AssertionError('No network')), \
             patch('subprocess.Popen',side_effect=AssertionError('No worker')):
            Assistant._respond(self.assistant,'chat1','Make a cinematic reel using this song and clips',
                               ['song','clip1','clip2'],None,'request1')
        self.assertEqual('complete',self.assistant.data['status'],self.assistant.data.get('stage'))
        self.assertEqual(1,len(self.assistant.state.cinematic.starts))
        self.assertEqual('full creator guide',seen[0]['feedback'])
        self.assertEqual(['song','clip1','clip2'],[s['id'] for s in brain.calls[0][1]['sources']])

    def test_model_selects_exact_ids_and_corrects_invalid_answer_once(self):
        bad=prepared();bad['steps'][0]['options']['music_source_id']='invented-path.mp3'
        brain=BoundaryBrain([bad,prepared()])
        result=plan_request(brain,'Make a cinematic reel',[],source_catalog(self.selected),{'owner':'keep'})
        self.assertEqual(2,len(brain.calls))
        self.assertEqual('song',result['steps'][0]['options']['music_source_id'])
        self.assertEqual({'owner':'keep'},brain.calls[0][1]['shared_memory'])
        self.assertIn('music_source_id',brain.calls[0][2]['properties']['steps']['items']['properties']['options']['properties'])

    def test_schema_and_validator_reject_unsupported_modes_extra_effects_and_bounds(self):
        self.assertIn('music_source_id',schema()['properties']['steps']['items']['properties']['options']['properties'])
        for options in ({'music_out':0},{'shot_source_ids':['clip1','clip1']},{'max_shots':101},
                        {'music_in':float('nan')},{'effects':['zoom']},{'shot_source_ids':'clip1'}):
            value=prepared();value['steps'][0]['options'].update(options)
            with self.subTest(options=options),self.assertRaises(ValueError):validate_plan(value)
        mixed=prepared();mixed['steps'].append(dict(tool='publish',options={}))
        with self.assertRaises(ValueError):validate_plan(mixed)

    def test_controller_runs_existing_services_with_continuous_original_music(self):
        result=self.run_creative()
        beats=self.assistant.state.beats.starts[0][0]
        cine=self.assistant.state.cinematic.starts[0][0]
        self.assertEqual(self.selected[0]['path'],beats['path'])
        self.assertEqual(1,beats['speed'])
        self.assertEqual(BEAT_ID,cine['beat_id'])
        self.assertEqual([s['path'] for s in self.selected[1:]],cine['source_paths'])
        self.assertFalse(cine['split_music'])
        self.assertEqual([],cine['effects'])
        self.assertFalse(cine['allow_slow']);self.assertFalse(cine['allow_fast'])
        self.assertEqual('complete',self.assistant.data['status'])
        self.assertTrue(Path(result['page']).is_file())
        self.assertEqual([result['preview']],self.assistant.data['last_paths'])

    def test_markers_only_never_starts_cinematic_render(self):
        result=self.run_creative(prepared('beats'))
        self.assertEqual([],self.assistant.state.cinematic.starts)
        self.assertEqual(1,len(result['beat_plan']['beats']))
        self.assertEqual([],self.assistant.data.get('last_paths',[]))

    def test_stop_before_submission_creates_no_service_job(self):
        self.assistant.stopped=True
        self.run_creative()
        self.assertEqual([],self.assistant.state.beats.starts)
        self.assertEqual([],self.assistant.state.cinematic.starts)

    def test_unknown_music_clip_ids_and_changed_sources_stop_before_submission(self):
        for key,value in [('music_source_id','unknown'),('shot_source_ids',['song'])]:
            parsed=prepared();parsed['steps'][0]['options'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_creative(parsed)
        self.assertEqual([],self.assistant.state.beats.starts)

    def test_saved_result_reopens_after_service_restart_without_duplicate(self):
        result=self.run_creative()
        count=len(self.assistant.state.beats.starts)
        self.assertTrue(followup(self.assistant,'chat1','Show my cinematic result',lambda _:None,pause=lambda _:None))
        self.assertEqual(count,len(self.assistant.state.beats.starts))
        self.assertEqual(1,len(self.assistant.state.cinematic.starts))
        self.assertEqual(result['preview'],self.assistant.messages[-1]['videos'][0])

    def test_pending_receipt_blocks_another_new_request_and_status_view_is_read_only(self):
        self.assistant.state.beats.states=['running']
        ticks=iter([0,1])
        self.run_creative(monotonic=lambda:next(ticks),max_wait=.5)
        with self.assertRaisesRegex(ValueError,'pending|uncertain'):self.run_creative()
        self.assertTrue(followup(self.assistant,'chat1','Show my cinematic result',lambda _:None,pause=lambda _:None))
        self.assertEqual(1,len(self.assistant.state.beats.starts))
        self.assertEqual([],self.assistant.state.cinematic.starts)

    def test_receipt_cannot_be_reopened_under_a_different_profile(self):
        self.run_creative();self.assistant.data['profile']='cricket'
        with self.assertRaisesRegex(ValueError,'profile'):
            followup(self.assistant,'chat1','Show my cinematic result',lambda _:None,pause=lambda _:None)

    def test_unexpected_result_path_is_rejected_before_opening_or_writing_a_report(self):
        outside=self.root/'outside.mp4';outside.write_bytes(b'synthetic')
        self.assistant.state.cinematic.result['preview']=str(outside)
        with self.assertRaisesRegex(ValueError,'unexpected'):self.run_creative()
        self.assertFalse((self.root/'assistant-review.html').exists())

    def test_beat_disk_result_reopens_without_resubmitting_when_memory_lost(self):
        self.run_creative(prepared('beats'))
        self.assistant.state.beats.states=['missing'];self.assistant.state.beats.polls=0
        self.assertTrue(followup(self.assistant,'chat1','Reopen my beat result',lambda _:None,pause=lambda _:None))
        self.assertEqual(1,len(self.assistant.state.beats.starts))

    def test_stop_waiting_for_beats_is_honest_and_does_not_claim_engine_cancelled(self):
        original=self.assistant.state.beats.start
        def submitted(payload,**kwargs):
            result=original(payload,**kwargs);self.assistant.stopped=True;return result
        self.assistant.state.beats.start=submitted;self.assistant.state.beats.states=['running']
        self.run_creative(prepared('beats'))
        self.assertEqual([],self.assistant.state.beats.cancels)
        self.assertEqual('stopped',self.assistant.data['status'])
        self.assertIn('may continue',self.assistant.data['stage'])
        self.assertEqual([],self.assistant.state.cinematic.starts)

    def test_show_after_stop_does_not_submit_the_remaining_cinematic_stage(self):
        original=self.assistant.state.beats.start
        def submitted(payload,**kwargs):
            result=original(payload,**kwargs);self.assistant.stopped=True;return result
        self.assistant.state.beats.start=submitted;self.assistant.state.beats.states=['running']
        self.run_creative()
        self.assistant.stopped=False;self.assistant.state.beats.states=['complete'];self.assistant.state.beats.polls=0
        self.assertTrue(followup(self.assistant,'chat1','Show my cinematic result',lambda _:None,pause=lambda _:None))
        self.assertEqual([],self.assistant.state.cinematic.starts)

    def test_interrupted_continuation_submission_is_never_repeated(self):
        ticks=iter([0,1,2])
        self.assistant.state.beats.states=['running']
        self.run_creative(monotonic=lambda:next(ticks),max_wait=.5)
        self.assistant.state.beats.states=['complete'];self.assistant.state.beats.polls=0
        calls=[]
        def lost(*args,**kwargs):calls.append(1);raise TimeoutError('Synthetic lost reply')
        self.assistant.state.cinematic.start=lost
        with self.assertRaises(TimeoutError):followup(self.assistant,'chat1','Continue my cinematic reel',lambda _:None,pause=lambda _:None)
        with self.assertRaisesRegex(ValueError,'uncertain|review'):
            followup(self.assistant,'chat1','Continue my cinematic reel',lambda _:None,pause=lambda _:None)
        self.assertEqual([1],calls)

    def test_changed_inputs_between_beat_completion_and_assembly_block(self):
        self.assistant.state.beats.states=['running','complete']
        def change(_):Path(self.selected[1]['path']).write_bytes(b'changed fixture input')
        with self.assertRaisesRegex(ValueError,'changed'):
            execute(self.assistant,'chat1',prepared(),self.selected,'gaming',lambda _:None,pause=change)
        self.assertEqual([],self.assistant.state.cinematic.starts)

    def test_saved_receipt_contains_model_tool_and_redacted_prompt_lineage(self):
        brain=BoundaryBrain([prepared()])
        parsed=plan_request(brain,'Make a cinematic reel',[],source_catalog(self.selected),{'access_token':'do-not-store','creator':'full',
                            'nested':{'client_secret':'hide-this','aws_secret_access_key':'also-hide'}})
        self.run_creative(parsed)
        pointer=self.assistant.data['creative_job']
        record=json.loads((self.root/'output'/'assistant-creative'/(pointer['id']+'.json')).read_text('utf-8'))
        self.assertEqual('[redacted]',record['model']['prompt_data']['shared_memory']['access_token'])
        self.assertEqual(['beats.start','cinematic.start'],[e['tool'] for e in record['executions']])
        self.assertEqual('full',record['model']['prompt_data']['shared_memory']['creator'])
        self.assertNotIn('hide-this',json.dumps(record));self.assertNotIn('also-hide',json.dumps(record))
        self.assertTrue(record['model']['intervention'])

    def test_actual_cinematic_snapshot_reopens_completed_metadata_without_constructor(self):
        from hinglish_cinematic.service import CinematicService
        self.run_creative()
        folder=self.root/'output'/'cinematic-reels'/CINE_ID
        result=self.assistant.state.cinematic.result
        (folder/'completed-reel.json').write_text(json.dumps(dict(id=CINE_ID,status='complete',result=result)),'utf-8')
        receiver=SimpleNamespace(jobs={},lock=threading.RLock(),folder=self.root/'output'/'cinematic-reels')
        self.assistant.state.cinematic.snapshot=lambda identity:CinematicService.snapshot(receiver,identity)
        self.assertTrue(followup(self.assistant,'chat1','Reopen my cinematic result',lambda _:None,pause=lambda _:None))
        self.assertEqual(1,len(self.assistant.state.cinematic.starts))

    def test_cinematic_stop_requests_existing_cancel_without_new_job(self):
        self.assistant.state.cinematic.states=['running']
        def stop_when_polling(_):self.assistant.stopped=True
        execute(self.assistant,'chat1',prepared(),self.selected,'gaming',lambda _:None,pause=stop_when_polling)
        self.assertEqual([CINE_ID],self.assistant.state.cinematic.cancels)
        self.assertEqual(1,len(self.assistant.state.cinematic.starts))

    def test_uncertain_submission_receipt_blocks_automatic_resubmission(self):
        def fail_after_submission(*a,**k):raise TimeoutError('Synthetic uncertain service start')
        self.assistant.state.beats.start=fail_after_submission
        with self.assertRaises(TimeoutError):self.run_creative()
        receipt=self.assistant.data['creative_job']
        self.assertIn('id',receipt)
        with self.assertRaisesRegex(ValueError,'uncertain|review'):
            followup(self.assistant,'chat1','Continue my cinematic reel',lambda _:None,pause=lambda _:None)

    def test_no_publishing_native_or_external_runtime_dependency(self):
        import builtins
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if any(part in name for part in ('providers','local_browser','openai','ollama')) or name.startswith('mcp__rea'):
                raise AssertionError('Forbidden boundary dependency: '+name)
            return original(name,*args,**kwargs)
        with patch('socket.socket',side_effect=AssertionError('No network')), \
             patch('subprocess.Popen',side_effect=AssertionError('No subprocess')), \
             patch('builtins.__import__',side_effect=guarded):
            self.run_creative()


if __name__=='__main__':unittest.main()
