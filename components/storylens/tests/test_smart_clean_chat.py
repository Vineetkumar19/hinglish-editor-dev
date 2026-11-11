"""Regressions from the owner's live raw-take editing workflow."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from hinglish_app.assistant_campaign import requested
from hinglish_app.assistant_sources import named_sources


class SmartCleanChatTests(unittest.TestCase):
    def test_cleanup_continuation_has_a_small_local_planner(self):
        from hinglish_app.assistant_clean_plan import requested as clean_requested,plan
        text='Run Smart Clean on the video you just arranged. Remove silence and keep the script order and selected takes.'
        self.assertTrue(clean_requested(text,True))
        self.assertFalse(clean_requested(text,False))
        self.assertFalse(clean_requested(text+' Publish it.',True))
        with tempfile.TemporaryDirectory() as folder:
            brain=Mock(root=Path(folder))
            brain.json.return_value={'reply':'Starting Smart Clean.','question':'','combine':True,
                'steps':[{'tool':'clean','options':{}}]}
            result=plan(brain,text,[],{'editing_sources':[{'id':'latest','title':'Script Edit output'}]})
            self.assertEqual(result['steps'],[{'tool':'clean','options':{}}])
            self.assertEqual(brain.json.call_args.kwargs['max_tokens'],400)
            self.assertIn('Latest completed video',brain.json.call_args.args[1]['active_input'])

    def test_script_result_uses_the_actual_phase2_export_name(self):
        from hinglish_app.assistant_media import outputs
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'output'/'phase2'/'run';out.mkdir(parents=True)
            xml=out/'EDITED_SEQUENCE.xml';xml.write_text('<xmeml/>')
            rendered=out/'script-001.mp4';rendered.touch()
            with patch('hinglish_app.assistant_media.render_xml',return_value=str(rendered)) as render:
                result=outputs(root,{'tool':'script'},{'folder':str(out),'xml_files':[str(xml)]},out)
            self.assertEqual(result,[str(rendered.resolve())])
            self.assertEqual(Path(render.call_args.args[0]),xml)

    def test_local_clean_with_publishing_exclusions_is_not_a_campaign(self):
        text=(r'Run Smart Clean on D:\Full Drive\thisis.vineet\e3. '
              'Select only the raw video files whose names start with VID; '
              'remove silence and repeated takes, then combine the clips. '
              'Do not upload, publish, schedule, add captions, or add music.')
        self.assertFalse(requested(text))
        self.assertFalse(requested('Arrange these clips with Script Edit, then Smart Clean. Never schedule them.'))

    def test_explicit_daily_shorts_workflow_remains_eligible(self):
        self.assertTrue(requested('Extract seven shorts and schedule them every day.'))
        self.assertTrue(requested('Create clips for a daily campaign, without captions.'))

    def test_owner_prefix_selects_raw_batch_without_finished_exports_or_subfolders(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('VID_002.mp4','VID_001.mp4','vid_003.MOV','final.mp4','edited.mp4','VID_notes.txt'):
                (root/name).touch()
            (root/'nested').mkdir();(root/'nested'/'VID_004.mp4').touch()
            result=named_sources(f'Edit clips from this folder:\n{root}\nUse only video files whose filenames start with VID. First use Script Edit, then Smart Clean.')
            self.assertEqual([p.name for p in result],['VID_001.mp4','VID_002.mp4','vid_003.MOV'])
            self.assertEqual(len(list(root.iterdir())),7)

    def test_missing_prefix_does_not_fall_back_to_finished_video(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'final.mp4').touch()
            with self.assertRaisesRegex(ValueError,'No video filenames start'):
                named_sources(f'{root}\nSelect only the raw video files whose names start with VID.')

    def test_script_planning_fits_with_full_creator_profile_and_eleven_clips(self):
        from hinglish_app.assistant_take_plan import requested as take_requested,plan
        from hinglish_niche.profiles import use,inject
        attachments=[{'name':'reference.txt','kind':'.txt'}]+[
            {'name':f'VID_{i:03d}.mp4','kind':'.mp4'} for i in range(11)]
        profile={'profile':'gaming','brief':'Preserve all creator guidance. '*450,
                 'feedback':'Keep actual spoken language and original sources.'}
        with tempfile.TemporaryDirectory() as folder,use(profile):
            brain=Mock(root=Path(folder))
            brain.json.return_value={'reply':'Arranging the supplied takes.','question':'',
                'combine':True,'steps':[{'tool':'script','options':{}}]}
            text='Use Script Edit only to arrange and combine these clips by the attached approximate script.'
            self.assertTrue(take_requested(text,attachments))
            result=plan(brain,text,[],attachments,{})
            system,data,schema=brain.json.call_args.args
            _,payload=inject(system,data,root=Path(folder))
            self.assertEqual(payload['creator_profile'],profile)
            self.assertEqual(data['attachments'],attachments)
            self.assertEqual(schema['properties']['steps']['items']['properties']['tool']['enum'],['script'])
            self.assertEqual(schema['properties']['steps']['minItems'],1)
            self.assertEqual(schema['properties']['question']['enum'],[''])
            self.assertEqual(result['steps'],[{'tool':'script','options':{}}])

    def test_local_model_corrects_a_premature_clean_step(self):
        from hinglish_app.assistant_take_plan import plan,requested as take_requested
        attachments=[{'name':'reference.txt','kind':'.txt'}]
        with tempfile.TemporaryDirectory() as folder:
            brain=Mock(root=Path(folder))
            brain.json.side_effect=[
                {'reply':'Arranging.','question':'','combine':True,
                 'steps':[{'tool':'script','options':{}},{'tool':'clean','options':{}}]},
                {'reply':'Arranging.','question':'','combine':True,'steps':[{'tool':'script','options':{}}]}]
            result=plan(brain,'Script Edit only. Smart Clean will be requested next.',[],attachments,{})
            self.assertEqual(brain.json.call_count,2)
            self.assertEqual([s['tool'] for s in result['steps']],['script'])
            self.assertFalse(take_requested('Use Script Edit and publish the result.',attachments))

    def test_ready_inputs_cannot_become_another_readiness_question_or_old_refusal(self):
        from hinglish_app.assistant_take_plan import plan
        for reply in ('Are you ready to start Script Edit?', 'The previous context was too large.'):
            with self.subTest(reply=reply),tempfile.TemporaryDirectory() as folder:
                brain=Mock(root=Path(folder))
                brain.json.side_effect=[
                    {'reply':reply,'question':reply,'combine':False,'steps':[]},
                    {'reply':'Starting Script Edit.','question':'','combine':True,
                     'steps':[{'tool':'script','options':{}}]}]
                result=plan(brain,'Start Script Edit now. Script Edit only.',[],
                    [{'name':'reference.txt','kind':'.txt'},{'name':'VID_001.mp4','kind':'.mp4'}],{})
                self.assertEqual(brain.json.call_count,2)
                self.assertEqual(result['steps'],[{'tool':'script','options':{}}])
                self.assertIn('explicitly asked to start',brain.json.call_args.args[1]['validation_error'])

    def test_local_model_corrects_clean_before_script(self):
        from hinglish_app.assistant_take_plan import plan
        attachments=[{'name':'reference.txt','kind':'.txt'},{'name':'VID_001.mp4','kind':'.mp4'}]
        with tempfile.TemporaryDirectory() as folder:
            brain=Mock(root=Path(folder))
            brain.json.side_effect=[
                {'reply':'Starting.','question':'','combine':True,
                 'steps':[{'tool':'clean','options':{}},{'tool':'script','options':{}}]},
                {'reply':'Arranging, then cleaning.','question':'','combine':True,
                 'steps':[{'tool':'script','options':{}},{'tool':'clean','options':{}}]}]
            result=plan(brain,'Start Script Edit, then Smart Clean and combine.',[],attachments,{})
            self.assertEqual(brain.json.call_count,2)
            self.assertEqual([step['tool'] for step in result['steps']],['script','clean'])
            self.assertIn('do not clean before arranging',brain.json.call_args.args[1]['validation_error'])


if __name__ == '__main__':
    unittest.main()
