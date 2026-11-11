import unittest
from pathlib import Path
from hinglish_app.user_messages import problem,publication_result,extracted


class MessagesTests(unittest.TestCase):
    def test_windows_commit_exhaustion_is_a_memory_problem_not_a_settings_error(self):
        raw='The paging file is too small for this operation to complete. (os error 1455)'
        issue=problem(RuntimeError(raw))
        self.assertEqual(issue['code'],'memory_full')
        self.assertIn(raw,issue['details'])
        self.assertNotIn('selected files and settings',issue['message'])

    def test_failures_explain_the_problem_and_keep_original_diagnostics(self):
        for raw,code in [('500 Server Error for url: http://127.0.0.1:11434/api/chat','local_service_error'),
                         ('CUDA out of memory','memory_full'),('No tab with id: 123','browser_tab_closed'),
                         ('Account changed. No upload was started on a different account.','instagram_account')]:
            with self.subTest(code=code):
                result=problem(raw)
                self.assertEqual(result['code'],code);self.assertEqual(result['details'],raw)
                self.assertNotEqual(result['message'],raw)
        self.assertIn('unavailable',problem('Job not found',404)['message'])

    def test_specific_causes_are_explained_before_generic_transport_errors(self):
        cases=[('HTTP 400: request exceeds the available context size (8192 tokens)','model_context_full'),
            ('login_required','sign_in_required'),('Ollama is missing storylens-meaning:14b','model_missing'),
            ('[WinError 112] There is not enough space on the disk','disk_full'),
            ('moov atom not found','media_unreadable'),('The recognizer returned invalid placeholder text','transcript_unreliable')]
        for text,code in cases:
            with self.subTest(code=code):
                result=problem(text);self.assertEqual(result['code'],code)
                self.assertGreater(len(result['message'].split('. ')),1)

    def test_unknown_exceptions_do_not_show_just_code_or_claim_an_upload_failed(self):
        for error in (KeyError('source_id'),TypeError('expected str, got None'),RuntimeError('unexpected internal state')):
            with self.subTest(error=error):
                result=problem(error,500)
                self.assertNotEqual(result['message'],str(error));self.assertIn(type(error).__name__,result['details'])
        result=problem(TimeoutError('request timed out'))
        self.assertIn('may still be processing',result['message'])
        self.assertNotIn('not uploaded',result['message'])

    def test_broll_native_connection_has_the_specific_next_action(self):
        result=problem(ValueError('Open Storylens in this editor, connect the intended timeline, then open its saved B-roll collection.'))
        self.assertEqual(result['code'],'broll_editor_connection')
        self.assertIn('B-roll',result['message']);self.assertIn('one',result['message'])

    def test_details_hide_connection_keys_and_preserve_useful_diagnostics(self):
        result=problem('500 Server Error http://127.0.0.1/api?token=secret-value&item=123 Authorization: Bearer private-key')
        self.assertNotIn('secret-value',result['details']);self.assertNotIn('private-key',result['details'])
        self.assertIn('item=123',result['details'])

    def test_feature_error_keeps_the_feature_and_processing_cause(self):
        from hinglish_app.user_messages import failure
        result=failure(FileNotFoundError('missing.mp4'),feature='Long to Shorts')
        self.assertTrue(result['error'].startswith('Long to Shorts stopped.'))
        self.assertEqual(result['error_code'],'file_missing')
        self.assertIn('missing.mp4',result['error_details'])

    def test_results_report_only_platforms_that_were_actually_requested_and_verified(self):
        self.assertEqual(extracted(1),'1 Short extracted.')
        review={'ids':[],'instagram_rows':[{'status':'published','account':'cricket'}]}
        self.assertEqual(publication_result(review),'1 video posted to Instagram (@cricket).')
        self.assertNotIn('YouTube',publication_result(review))
        review['instagram_rows'][0]['status']='queued'
        self.assertEqual(publication_result(review),'')
        self.assertIn('nothing uploaded',publication_result({**review,'youtube_check_only':True}))

    def test_every_feature_page_loads_shared_error_handling_before_feature_scripts(self):
        for page in (Path(__file__).parents[1]/'hinglish_app/static').glob('*.html'):
            with self.subTest(page=page.name):
                html=page.read_text('utf-8')
                self.assertIn('feedback.js',html)
                self.assertLess(html.index('feedback.js'),html.index('</head>'))

    def test_retry_reports_one_new_post_separately_from_an_earlier_receipt(self):
        from hinglish_app.pipeline_ledger import outcome
        review={'ids':[],'instagram_rows':[
            {'id':'first','status':'published','account':'cricket','url':'https://www.instagram.com/reel/first/',
             'previously_published':True},
            {'id':'second','status':'published','account':'cricket','url':'https://www.instagram.com/reel/second/',
             'previously_published':False}]}
        result=publication_result(review)
        self.assertIn('1 new video posted to Instagram',result)
        self.assertIn('1 video was already posted earlier and not uploaded again',result)
        self.assertNotIn('2 videos posted',result)
        status=outcome(review)
        self.assertTrue(status['complete'])
        self.assertEqual(status['summary'],'1 Instagram newly posted · 1 Instagram posted earlier')
        review['instagram_rows'][1]['previously_published']=True
        self.assertIn('No new Instagram videos were uploaded',publication_result(review))
