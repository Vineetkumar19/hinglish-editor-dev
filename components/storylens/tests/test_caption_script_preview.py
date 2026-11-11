import json
from pathlib import Path
import tempfile
import unittest

from hinglish_captions.script_preview import script_cues,create_script_preview
from hinglish_captions.project import cues_to_data
from hinglish_captions.editing import apply_timings
from hinglish_app.user_messages import problem


class CaptionScriptPreviewTests(unittest.TestCase):
    def test_exact_words_line_boundaries_and_saveable_timings(self):
        text='Apni kahani share karo\nBuild something extraordinary today.'
        cues=script_cues(text,30,'caption_2')
        self.assertEqual([q.text for q in cues],text.splitlines())
        self.assertEqual(cues[-1].end,30)
        self.assertEqual([q.template_slot for q in cues],[0,1])
        self.assertEqual(apply_timings(cues,cues_to_data(cues),30),cues)

    def test_validation_uses_shared_plain_language_errors(self):
        self.assertEqual(problem(ValueError('Caption preview service needs an update'))['code'],'caption_preview_service_outdated')
        for text,duration,message in [('',30,'caption_preview_text_required'),('x'*6001,30,'caption_preview_text_too_long'),('word '*100,3,'caption_preview_duration_invalid')]:
            with self.subTest(message=message):
                with self.assertRaises(ValueError) as caught:script_cues(text,duration,'caption_2')
                self.assertEqual(problem(caught.exception)['code'],message)

    def test_new_projects_keep_exact_text_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);payload={'text':'Your content needs focus.\nApni story share karo.','style':'serif_circle_draft','duration':5,'format':'square'}
            first=create_script_preview(root,payload);second=create_script_preview(root,payload)
            self.assertNotEqual(first['url'],second['url'])
            folder=root/'output/captions/script-previews'/first['url'].split('/')[-2]
            project=json.loads((folder/'caption-project.json').read_text('utf-8'))
            self.assertEqual(project['reference_script'],payload['text'])
            self.assertEqual((project['width'],project['height']),(720,720))
            self.assertTrue(project['script_preview'])
            self.assertTrue(project['preview_stale'])
            self.assertIn('Change script',(folder/'report.html').read_text('utf-8'))


if __name__=='__main__':unittest.main()
