import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_aigen.settings import GenSettings
from hinglish_aivideo.studio import analyse_reference,capabilities,run_motion,motion_script

ROOT=Path(__file__).resolve().parents[1]

class VideoStudioTests(unittest.TestCase):
    def test_methods_validate_before_generation(self):
        with self.assertRaisesRegex(ValueError,'reference missing'):
            GenSettings(kind='video',video_method='reference')
        with self.assertRaisesRegex(ValueError,'method unavailable'):
            GenSettings(kind='video',video_method='arbitrary-code')
        self.assertEqual(GenSettings(kind='video',video_method='motion',quality='preview').quality,'preview')

    def test_motion_method_bypasses_wan_and_keeps_a_real_method_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-studio-') as tmp:
            folder=Path(tmp);self.assertTrue(folder.resolve().is_relative_to(ROOT))
            result=folder/'report.html';result.write_text('saved renderer review','utf8')
            with patch('hinglish_motion.pipeline.run',return_value=result) as run:
                self.assertEqual(run_motion(ROOT,None,'Create and share.',GenSettings(kind='video',video_method='motion',motion_style='orbit',quality='preview'),lambda _:None),result)
            setting=run.call_args.args[3]
            self.assertEqual(setting.style,'theme:orbit');self.assertEqual(setting.quality,'preview')
            self.assertTrue(setting.preserve_script_text)
            receipt=json.loads((folder/'ai-video-production.json').read_text('utf8'))
            self.assertIn('Three.js / ThreeUI',receipt['tools']);self.assertFalse(receipt['native_3d_editability'])

    def test_reference_rejects_arbitrary_urls_before_reader_or_download(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-ref-') as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT))
            with patch('subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'reference unsupported'):
                    analyse_reference(ROOT,'https://127.0.0.1/private',tmp)
                run.assert_not_called()

    def test_reference_analysis_keeps_existing_selected_style_and_requires_vision(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-ref-') as tmp:
            folder=Path(tmp);self.assertTrue(folder.resolve().is_relative_to(ROOT))
            source=folder/'sample.mp4';source.write_bytes(b'test fixture, not a real video')
            profile=folder/'profile.json';profile.write_text(json.dumps({'name':'sample','source_sha256':'abc','measured':{},'visual_reading':None}),'utf8')
            with patch('hinglish_cut.reelmimic.learn',return_value=profile) as learn:
                with self.assertRaisesRegex(RuntimeError,'vision unavailable'):
                    analyse_reference(ROOT,str(source),folder,lambda _:None)
                self.assertFalse(learn.call_args.kwargs['select'])

    def test_preview_reaches_the_worker_without_requiring_a_full_render(self):
        from hinglish_aigen.pipeline import make_clips
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-preview-') as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT))
            moments=[{'index':1,'prompt':'A paper boat floating on a quiet stream.','motion':'Slow tracking shot','chosen':''}]
            with patch('hinglish_aigen.engine.generate',return_value={}) as generate:
                make_clips(ROOT,Path(tmp),moments,'cinematic','9:16',None,lambda _:None,False,'preview')
            item=generate.call_args.args[1][0]
            self.assertEqual((item['width'],item['height'],item['frames']),(480,832,49))
            self.assertEqual(generate.call_args.kwargs['mode'],'low')

    def test_capability_labels_distinguish_rendered_3d(self):
        data=capabilities(ROOT)
        self.assertEqual([r['id'] for r in data['methods']],['generative','reference','motion'])
        self.assertTrue(any('rendered video' in s for s in data['limits']))

    def test_motion_schema_enforces_the_same_word_limits_as_the_renderer(self):
        from types import SimpleNamespace
        from hinglish_motion.creative import plan_creative
        from hinglish_motion.settings import MotionSettings
        captured={}
        def answer(system,payload,schema,**kwargs):
            captured.update(schema['properties']['scenes']['items']['properties'])
            return {'scenes':[{'line':0,'template':'orbital_title',
                'title':{'start':0,'count':6},'label':{'start':6,'count':2},
                'value':{'start':0,'count':0},'items':[],'assets':[],
                'motion':'rise','depth':True,'title_words':6}]}
        brain=SimpleNamespace(json=answer)
        line=SimpleNamespace(id=0,start=0,text='Turn a simple plan into a clear story.')
        settings=MotionSettings(style='theme:orbit',preserve_script_text=True)
        scene=plan_creative(brain,[line],settings,lambda _:None)[0]
        self.assertEqual(scene.data['title']+' '+scene.data['label'],line.text)
        self.assertEqual(captured['title']['properties']['count']['maximum'],6)
        self.assertEqual(captured['value']['properties']['count']['maximum'],3)
        self.assertEqual(captured['items']['items']['properties']['count']['maximum'],7)
        def cut_words(*args,**kwargs):
            result=answer(*args,**kwargs)
            result['scenes'][0]['title']={'start':1,'count':6}
            result['scenes'][0]['label']={'start':0,'count':0}
            return result
        brain.json=cut_words
        fixed=plan_creative(brain,[line],settings,lambda _:None)[0]
        self.assertEqual(fixed.data['title']+' '+fixed.data['label'],line.text)

    def test_long_motion_scripts_paginate_without_losing_words(self):
        source=' '.join('word'+str(i) for i in range(49))
        rendered=motion_script(source)
        self.assertEqual(rendered.split(),source.split())
        self.assertTrue(all(2<=len(line.split())<=12 for line in rendered.splitlines()))

    def test_reference_vision_reuses_the_parent_gpu_reservation(self):
        from contextlib import nullcontext
        from PIL import Image
        from hinglish_cut.reelmimic import learn
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-gpu-') as tmp:
            folder=Path(tmp);self.assertTrue(folder.resolve().is_relative_to(ROOT))
            source=folder/'reference.png';Image.new('RGB',(32,32),'green').save(source)
            with patch('hinglish_motion.style.reference_frames',return_value=([source],None)), \
                 patch('hinglish_motion.style.palette',return_value=['#000000']), \
                 patch('hinglish_motion.style.tokens_from_palette',return_value=({'text':'#ffffff'},{})), \
                 patch('hinglish_motion.style.describe',return_value={'look':'green reference'}) as vision, \
                 patch('hinglish_cut.gpu_lock.gpu_lock',return_value=nullcontext()) as reserve:
                result=learn(folder/'app','aivideo',source,gpu_already_held=True)
                reserve.assert_not_called();vision.assert_called_once()
                self.assertEqual(json.loads(result.read_text('utf8'))['visual_reading']['look'],'green reference')
                cached=json.loads(result.read_text('utf8'));cached['visual_reading']=None
                cached['owner_guidance']='keep this saved knowledge'
                result.write_text(json.dumps(cached),'utf8')
                retried=learn(folder/'app','aivideo',source,gpu_already_held=True,retry_vision=True)
                recovered=json.loads(retried.read_text('utf8'))
                self.assertEqual(recovered['owner_guidance'],'keep this saved knowledge')
                self.assertEqual(recovered['visual_reading']['look'],'green reference')
                reserve.assert_not_called()
                learn(folder/'standalone','aivideo',source)
                reserve.assert_called_once()

    def test_scripted_motion_schema_uses_a_bounded_split_instead_of_lossy_word_ranges(self):
        from types import SimpleNamespace
        from jsonschema import Draft202012Validator
        from hinglish_motion.creative import plan_creative
        from hinglish_motion.settings import MotionSettings
        observed={'line':0,'template':'orbital_title','title':{'start':0,'count':6},
            'label':{'start':0,'count':0},'value':{'start':0,'count':0},
            'items':[],'assets':[],'motion':'rise','depth':True}
        schemas=[]
        def answer(system,payload,schema,**kwargs):
            schemas.append(schema)
            return {'scenes':[{**observed,'title_words':6}]}
        line=SimpleNamespace(id=0,start=0,text='Turn a simple plan into a clear story.')
        scenes=plan_creative(SimpleNamespace(json=answer),[line],
            MotionSettings(style='theme:orbit',preserve_script_text=True),lambda _:None)
        validator=Draft202012Validator(schemas[0])
        self.assertTrue(list(validator.iter_errors({'scenes':[observed]})),
            'The model grammar must reject the real response that omitted clear story.')
        self.assertFalse(list(validator.iter_errors({'scenes':[{**observed,'title_words':6}]})))
        self.assertEqual(scenes[0].data['title']+' '+scenes[0].data['label'],line.text)

    def test_reference_description_uses_configured_non_thinking_request_and_records_result(self):
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import Mock
        from hinglish_motion.style import describe
        reading={'typeface':'serif','texture':'clean','energy':'calm','mood':['fresh'],'summary':'Green garden titles.'}
        response=Mock();response.json.return_value={'message':{'content':json.dumps(reading)},'done_reason':'stop'}
        session=Mock();session.post.return_value=response
        judge=SimpleNamespace(model='configured-local-vision',session=session,url='http://local.invalid',close=Mock())
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='aivideo-reading-') as tmp:
            receipt=Path(tmp)/'vision-reading.json'
            with patch('hinglish_aigen.judge.Judge',return_value=judge), \
                 patch('hinglish_cut.model_preferences.configure_request',side_effect=lambda root,body:body.update(think=False)) as configure:
                result=describe(ROOT,[np.zeros((32,32,3),dtype=np.uint8)],lambda _:None,receipt_path=receipt)
            configure.assert_called_once()
            self.assertIs(session.post.call_args.kwargs['json']['think'],False)
            self.assertEqual(result,reading)
            self.assertEqual(json.loads(receipt.read_text('utf8'))['model'],'configured-local-vision')
            response.json.return_value={'message':{'content':'{}'},'done_reason':'length'}
            with patch('hinglish_aigen.judge.Judge',return_value=judge):
                self.assertIsNone(describe(ROOT,[np.zeros((32,32,3),dtype=np.uint8)],lambda _:None,receipt_path=receipt))

    def test_windows_wan_shards_use_the_non_mapped_loader(self):
        import importlib.util
        import sys
        from types import SimpleNamespace,ModuleType
        from unittest.mock import Mock
        spec=importlib.util.spec_from_file_location('studio_worker_test',ROOT/'tools/aigen/worker.py')
        worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
        transformer=SimpleNamespace(from_pretrained=Mock(side_effect=RuntimeError('load intercepted')))
        fake=ModuleType('diffusers')
        fake.AutoencoderKLWan=SimpleNamespace(from_pretrained=Mock(return_value=object()))
        fake.WanPipeline=object;fake.WanTransformer3DModel=transformer
        utilities=ModuleType('diffusers.utils');utilities.export_to_video=Mock()
        torch=SimpleNamespace(bfloat16='bf16',float8_e4m3fn='fp8')
        with patch.dict(sys.modules,{'diffusers':fake,'diffusers.utils':utilities}), \
             patch.object(worker,'encode_video_prompts',return_value={}), \
             patch.object(worker,'say'),patch.object(sys,'platform','win32'):
            with self.assertRaisesRegex(RuntimeError,'load intercepted'):
                worker.run_videos([],ROOT/'tools/aigen/install/models','low',torch)
        self.assertIs(transformer.from_pretrained.call_args.kwargs.get('disable_mmap'),True)

if __name__=='__main__':unittest.main()
