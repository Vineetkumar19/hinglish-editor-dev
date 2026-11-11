import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from hinglish_app.server import AppState
from hinglish_app.assistant_caption_repair import requested


class CaptionRepairChatTests(unittest.TestCase):
    def test_new_instagram_upload_with_receipt_verification_is_not_receipt_only(self):
        from hinglish_app.assistant_instagram_verification import followup
        self.assertFalse(followup(None,'id',
            'Use only the second Short. Post it now on Instagram and verify the actual publication receipt.',{}))

    def test_release_time_correction_that_reuses_captions_is_not_a_caption_repair(self):
        text='Correct the Instagram release times for these same two DC Shorts: publish the first now and queue the second tomorrow at 7 p.m. IST. Reuse the saved captions.'
        self.assertFalse(requested(text))
        from hinglish_app.assistant_schedule_status import requested as status_requested
        self.assertFalse(status_requested(text+' Leave YouTube check-only.',
            {'publishing_review':{'schedule':True,'rows':[{'id':'draft'}],'youtube_check_only':True}}))

    def test_explicit_repair_and_resume_keeps_original_check_only_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);a=state.assistant;sid=a.create()['id']
            project=root/'output/shorts/run/dc/shorts-project.json';project.parent.mkdir(parents=True)
            project.write_text('{}','utf-8');clip=project.parent/'short.mp4';clip.touch()
            options={'distribution_platforms':'paired','distribution_profile':'gaming','first_date':'2030-01-01','clock':'19:00'}
            a._update(sid,profile='gaming',status='complete',shorts_paths=[str(clip)],
                pipeline={'steps':[{'tool':'distribute','options':options}],
                    'request':'Extract 2 Shorts. YouTube check only. Post on Instagram.',
                    'automatic':True,'phase':'attention'})
            with patch('hinglish_captions.repair_project.repair'), \
                 patch('hinglish_app.assistant_media.outputs',return_value=[str(clip)]), \
                 patch('hinglish_app.assistant_distribution.from_outputs') as handoff:
                a.send(sid,'Repair captions and headings, then resume the original publishing workflow.',profile='gaming')
                for _ in range(300):
                    if handoff.called:break
                    time.sleep(.01)
            handoff.assert_called_once()
            self.assertEqual(handoff.call_args.args[2],options)
            self.assertIn('YouTube check only',handoff.call_args.args[3])
            self.assertTrue(a.snapshot(sid)['pipeline']['automatic'])

    def test_normal_chat_uses_original_edit_project_without_extraction_upload_or_double_captions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=AppState(root);a=state.assistant;sid=a.create()['id']
            project=root/'output/shorts/run/mi/shorts-project.json';project.parent.mkdir(parents=True)
            project.write_text('{}','utf-8');clips=[str(project.parent/f'short-{i}.mp4') for i in (1,2)]
            for clip in clips:Path(clip).touch()
            prior={'id':'previous','state':'complete','ids':[],'rows':[]}
            a._update(sid,profile='gaming',status='complete',shorts_paths=clips,last_paths=clips,publishing_review=prior)
            with patch('hinglish_captions.repair_project.repair') as repair,\
                 patch('hinglish_app.assistant_media.outputs',return_value=clips),\
                 patch.object(state,'create_job') as extract,\
                 patch('hinglish_app.assistant_publish.start') as publish:
                a.send(sid,'Repair the captions and headings of my two saved MI Shorts. Do not upload.',profile='gaming')
                for _ in range(300):
                    current=a.snapshot(sid)
                    if current['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(current['status'],'complete',current.get('stage'))
            repair.assert_called_once()
            extract.assert_not_called();publish.assert_not_called()
            self.assertEqual(current['shorts_paths'],clips);self.assertIsNone(current['publishing_review'])
            self.assertEqual(current['prior_publishing_reviews'][0]['id'],'previous')

    def test_questions_and_exclusions_are_not_edits(self):
        self.assertFalse(requested('How do I repair captions?'))
        self.assertFalse(requested('Do not repair captions'))
        self.assertTrue(requested('Fix my saved Shorts captions and title'))


if __name__=='__main__':unittest.main()
