import copy
import tempfile
import unittest
from pathlib import Path


class ReferenceComposerTests(unittest.TestCase):
    def scene(self):
        return {'duration':3.,'background':'#eee9dd','camera_start':1.,'camera_end':1.08,
                'layers':[{'kind':'text','text':'A complete phrase','asset':'','x':.1,'y':.3,'w':.8,'h':.2,
                           'size':.08,'font':'sans','color':'#111111','align':'center','weight':700,
                           'opacity':1.,'rotation':0.,'delay':.1,'travel_x':0.,'travel_y':.04,
                           'scale_from':.95,'enter':.5,'drift_x':0.,'drift_y':0.,'shadow':.2}],
                'sound_intents':[{'time':.6,'query':'soft short whoosh','gain_db':-12.}]}

    def test_plan_accepts_measured_layers_without_changing_model_copy(self):
        from hinglish_motion.reference_composer import validate_scene
        scene=self.scene(); before=copy.deepcopy(scene)
        self.assertEqual(validate_scene(scene),before)
        self.assertEqual(scene,before)

    def test_image_slots_cannot_silently_disappear(self):
        from hinglish_motion.reference_composer import validate_scene
        scene=self.scene(); scene['layers'][0].update(kind='image',asset='a1',text='')
        with self.assertRaisesRegex(ValueError,'asset'):validate_scene(scene,assets={})
        self.assertEqual(validate_scene(scene,assets={'a1':{'src':'asset.png'}})['layers'][0]['asset'],'a1')

    def test_invalid_time_geometry_and_untrusted_code_are_rejected(self):
        from hinglish_motion.reference_composer import validate_scene
        for key,value in [('delay',9),('w',-1),('color','url(https://example.test)'),('x',float('nan')),('kind','script')]:
            scene=self.scene();scene['layers'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_scene(scene)
        scene=self.scene();scene['layers'][0]['onclick']='run()'
        with self.assertRaises(ValueError):validate_scene(scene)

    def test_local_sound_catalogue_is_read_only_and_ids_cannot_escape(self):
        from hinglish_motion.reference_composer import sound_catalogue,resolve_sound
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            p=Path(directory);(p/'soft whoosh.wav').write_bytes(b'RIFF');(p/'readme.txt').write_text('data')
            rows=sound_catalogue([p]);self.assertEqual(len(rows),1)
            self.assertEqual(resolve_sound(rows,rows[0]['id']),p/'soft whoosh.wav')
            with self.assertRaises(ValueError):resolve_sound(rows,'../../outside.wav')
            self.assertEqual(len(list(p.iterdir())),2)

    def test_chat_route_needs_explicit_reference_and_wont_turn_a_question_into_work(self):
        from hinglish_app.assistant_motion_reference import request
        text='Create one Motion Graphics reference example.\nReference: D:/samples/1.mp4\nSounds folder: D:/sounds'
        self.assertEqual(request(text)['reference'],'D:/samples/1.mp4')
        self.assertIsNone(request('Can Motion Graphics use a reference?'))
        self.assertIsNone(request('Do not create Motion Graphics.\nReference: D:/samples/1.mp4'))

    def test_storyboard_rejects_unsourceable_prompt_queries_and_cutout_backgrounds(self):
        from hinglish_motion.reference_composer import validate_storyboard
        plan={'scenes':[{'assets':[{'id':'a','kind':'photo','cutout':True,'query':'abstract geometric background'}]}]}
        with self.assertRaisesRegex(ValueError,'background'):validate_storyboard(plan)
        plan['scenes'][0]['assets'][0].update(kind='person',query='woman running',cutout=True)
        validate_storyboard(plan)
        plan['scenes'][0]['assets'][0]['query']='woman running, cinematic lighting, black and red, high contrast'
        with self.assertRaisesRegex(ValueError,'query'):validate_storyboard(plan)

    def test_offline_composition_preserves_asset_ids_and_escapes_text(self):
        from hinglish_motion.creative_export import build
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            p=Path(directory);asset=p/'owner.png';asset.write_bytes(b'fixture-only')
            scene=self.scene();scene['layers'][0]['text']='Literal <script> text'
            payload={'duration':3.,'template':'reference_layers','data':{'reference_scene':scene,
                     'assets':[{'id':'a1','src':asset.as_uri()}]}}
            folder=build(payload,p/'out.mp4',360,640,30)
            page=(folder/'index.html').read_text('utf-8')
            self.assertNotIn('Literal <script>',page)
            self.assertIn('\\u003cscript>',page)
            import json
            copied=json.loads((folder/'scene.json').read_text('utf-8'))['data']['assets'][0]
            self.assertEqual(copied['id'],'a1');self.assertTrue((folder/copied['src']).is_file())
            self.assertIn('reference_scene',(folder/'creative.js').read_text('utf-8'))

    def test_compiled_center_boxes_fit_without_rewriting_or_dropping_text(self):
        from hinglish_motion.reference_composer import compile_layer
        selected={'kind':'text','text':'A complete phrase','asset':'','cx':.85,'cy':.9,'w':.8,'h':.2,
                  'size':.08,'font':'sans','color':'#111111','align':'center','weight':700,
                  'opacity':1.,'rotation':0.,'delay':.1,'motion':'rise','shadow':.2}
        compiled=compile_layer(selected)
        self.assertEqual(compiled['text'],selected['text'])
        self.assertGreaterEqual(compiled['x'],0);self.assertLessEqual(compiled['x']+compiled['w'],1)
        self.assertGreaterEqual(compiled['y'],0);self.assertLessEqual(compiled['y']+compiled['h'],1)

    def test_resume_rejects_other_references_or_unapproved_asset_paths(self):
        from hinglish_motion.reference_composer import load_checkpoint
        import json
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            root=Path(directory);p=root/'output/motion/checkpoint';p.mkdir(parents=True)
            (p/'reused-analysis.json').write_text(json.dumps({'source_sha256':'one'}),'utf-8')
            with self.assertRaisesRegex(ValueError,'reference'):load_checkpoint(p,'two',root)
            (p/'local-storyboard-1.json').write_text(json.dumps({'answer':{'scenes':[]}}),'utf-8')
            (p/'asset-receipts.json').write_text(json.dumps([{'id':'a','file':'../../outside.png'}]),'utf-8')
            with self.assertRaises(ValueError):load_checkpoint(p,'one',root)

    def test_role_slots_cannot_replace_required_copy_with_images(self):
        from hinglish_motion.reference_slots import compile_slots
        selected={'cx':.5,'cy':.3,'w':.8,'h':.15,'size':.08,'font':'sans','color':'#111111',
                  'align':'center','weight':700,'rotation':0.,'delay':.1,'end':3.,'motion':'rise','shadow':.2}
        answer={'background':'#eee9dd','camera_start':1.,'camera_end':1.03,'slots':{'copy_0':selected,'asset_a1':selected},
                'backdrop_word':'','decorations':[],'sound_intents':[{'time':.5,'query':'soft whoosh','gain_db':-12.}]}
        scene=compile_slots(answer,['Complete words'],['a1'],3.)
        self.assertEqual([l['text'] for l in scene['layers'] if l['kind']=='text'],['Complete words'])
        self.assertEqual([l['asset'] for l in scene['layers'] if l['kind']=='image'],['a1'])
        del answer['slots']['copy_0']
        with self.assertRaises(ValueError):compile_slots(answer,['Complete words'],['a1'],3.)

    def test_editor_span_uses_decoded_frames_instead_of_unrounded_requested_seconds(self):
        from hinglish_motion.reference_run import frame_media
        from hinglish_cut.xml_export import export_xml
        from hinglish_cut.model import Cut
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            p=Path(directory);media=frame_media(p/'actual.mp4',517,30,360,640)
            export_xml(p/'timeline.xml',[Cut('1',0,517,0)],{'1':media})
            self.assertIn('<duration>517</duration>',(p/'timeline.xml').read_text('utf-8'))

    def test_local_export_error_does_not_claim_account_signin_is_required(self):
        from hinglish_app.user_messages import problem,catalog
        catalog.cache_clear()
        e=RuntimeError('Local LLM assigning required text/image slots. Invalid source bounds: Cut(media_id=1)')
        self.assertEqual(problem(e,feature='Motion graphics')['code'],'motion_reference_export')

    def test_reference_and_sound_paths_are_not_treated_as_source_video_folders(self):
        from hinglish_app.assistant import Assistant
        from unittest.mock import MagicMock,patch
        import threading
        owner=Assistant.__new__(Assistant);owner.root=Path(__file__).resolve().parents[1]
        owner.lock=threading.RLock();owner.snapshot=MagicMock(return_value={'messages':[],'attachments':[],'profile':'general'})
        owner._update_user_message=MagicMock();owner._update=MagicMock();owner._message=MagicMock()
        text='Create one Motion Graphics reference example by finalizing its existing saved video.\nReference: D:/samples/1.mp4\nSounds folder: D:/sounds'
        with patch('hinglish_niche.profiles.Profiles.context',return_value={'profile':'general'}), \
             patch('hinglish_app.assistant_publish_intent.preflight',return_value=text), \
             patch('hinglish_app.assistant_artifacts.editing_requested',return_value=True), \
             patch('hinglish_app.assistant_sources.named_sources',side_effect=ValueError('wrong folder role')) as sources, \
             patch('hinglish_app.assistant_motion_reference.execute',return_value=True) as reference:
            owner._respond('fixture',text,[],None,'message')
            reference.assert_called_once();sources.assert_not_called()


if __name__=='__main__':unittest.main()
