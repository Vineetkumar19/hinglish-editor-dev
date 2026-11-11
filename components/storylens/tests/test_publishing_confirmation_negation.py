import json,tempfile,unittest
from pathlib import Path
from hinglish_app.assistant_publish import confirmation

class PublishingConfirmationNegationTests(unittest.TestCase):
    def setUp(self):
        base=Path('output/publisher-retry-repair-20261029/test-temp');base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'config.workflow.local.json').write_text(json.dumps({'publishing_defaults':{'made_for_kids':False,'synthetic_media':False}}))
        self.review={'id':'current-review','state':'review','upload_requested':True}

    def test_explicit_upload_now_survives_unrelated_negated_edit_and_schedule(self):
        text='Upload that same one video now to Cricket YouTube and Instagram. Do not create new clips or schedule future posts. I authorize these two uploads now.'
        self.assertEqual(confirmation(text,self.review,self.root,execution=True),
            {'review':'current-review','made_for_kids':False,'synthetic_media':False})

    def test_actual_publication_refusals_and_questions_stay_blocked(self):
        for text in ['Do not upload this video.','Never publish this video.','Cancel these uploads.','How do I upload this?','Do not upload it. Upload it now.']:
            with self.subTest(text=text):self.assertIsNone(confirmation(text,self.review,self.root,execution=True))

    def test_saved_declarations_are_required_and_ordinary_reply_is_unchanged(self):
        self.assertIsNone(confirmation('Upload now. Do not make new clips.',self.review,self.root))
        (self.root/'config.workflow.local.json').write_text('{}')
        self.assertIsNone(confirmation('Upload now. Do not make new clips.',self.review,self.root,execution=True))

    def test_explicit_negative_disclosure_is_data_and_not_removed(self):
        (self.root/'config.workflow.local.json').write_text('{}')
        self.assertEqual(confirmation('Upload now, not made for kids, no synthetic media. Do not create clips.',self.review,self.root,execution=True),
            {'review':'current-review','made_for_kids':False,'synthetic_media':False})
        self.assertIsNone(confirmation('Do not create new clips.',self.review,self.root,execution=True))
