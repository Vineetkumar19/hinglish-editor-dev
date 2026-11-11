import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
from hinglish_app.support_call_actions import interpret, split_steps
from hinglish_app.support_call_router import decode_plan
from hinglish_app import support_call_local as local

class VoiceNavigationTests(TestCase):
    def setUp(self):
        metrics=patch.object(local,'_persist_metrics')
        metrics.start()
        self.addCleanup(metrics.stop)

    def test_owner_commands_and_conversational_requests(self):
        cases = {
            'Open auto caption.': 'captions',
            'Open B-roll, add B-roll feature.': 'broll',
            'Open Smart Visual.': 'visuals',
            'Can you take me into Auto Captions?': 'captions',
            'I want you to open Smart Visual.': 'visuals',
            'Could you bring up the B-roll feature?': 'broll',
            'ऑटो कैप्शन खोल दो': 'captions',
            'स्मार्ट विजुअल खोलो': 'visuals',
        }
        with patch('hinglish_app.support_call_actions._worker') as desktop:
            for sentence, tool in cases.items():
                with self.subTest(sentence=sentence):
                    steps = split_steps(sentence)
                    self.assertEqual(len(steps), 1)
                    self.assertEqual(interpret(Path.cwd(), steps[0], 'en', 'clean').action,
                                     {'type':'open_tool','tool':tool})
            desktop.assert_not_called()

    def test_desktop_apps_and_files_do_not_need_the_language_model(self):
        for sentence, expected in {
            'Open File Explorer': ('open', 'file explorer'),
            'Open Chrome browser': ('open', 'chrome'),
            'Open WhatsApp desktop': ('open', 'whatsapp'),
            'Open Adobe After Effects': ('open', 'after effects'),
            'Open Topaz': ('open', 'topaz video ai'),
            'Open Microsoft Excel': ('open', 'excel'),
            'Open file report.xlsx': ('path', 'report.xlsx'),
            'Open "D:/My Files/report.xlsx" in Excel': ('path', 'D:/My Files/report.xlsx'),
        }.items():
            with self.subTest(sentence=sentence), patch(
                'hinglish_app.support_call_actions._worker', return_value={'ok': True}
            ) as worker:
                self.assertTrue(interpret(Path.cwd(), sentence, 'en', 'clean').ok)
                self.assertEqual(worker.call_args.args, expected)
                if sentence.endswith('in Excel'):
                    self.assertEqual(worker.call_args.kwargs, {'app': 'excel'})

    def test_public_lookup_is_not_a_local_file_search(self):
        with patch('hinglish_app.support_call_actions._worker') as worker:
            self.assertIsNone(interpret(Path.cwd(), 'Search for Lionel Messi', 'en', 'clean'))
            worker.assert_not_called()

    def test_three_real_commands_stay_three(self):
        steps=split_steps('Open Auto Captions and then open B-roll and then open Smart Visuals')
        self.assertEqual(len(steps),3)

    def test_explanations_and_negations_do_not_execute(self):
        for question in ('What does Auto Caption do?', 'How do I open B-roll?',
                         'Do not open Smart Visual', "Don't open Chrome"):
            with self.subTest(question=question):
                self.assertIsNone(interpret(Path.cwd(),question,'en','clean'))

    def test_semantic_router_only_emits_known_targets(self):
        action,_,_=decode_plan(json.dumps({'intent':'open_tool','tool':'captions'}),'clean',[])
        self.assertEqual(action.action['tool'],'captions')
        for plan in ({'intent':'open_tool','tool':'not-a-tool'},
                     {'intent':'open_app','app':'powershell'},
                     {'intent':'click_button','tool':'introCreate','label':'Imaginary button'}):
            with self.assertRaises(ValueError):
                decode_plan(json.dumps(plan),'clean',[])
        action,_,_=decode_plan(json.dumps({'intent':'click_button','tool':'introCreate','label':'Play Intro'}),'clean',[])
        self.assertEqual(action.action['label'],'Play intro')

    def test_top_bar_and_nested_commands_use_the_current_workspace(self):
        cases = [
            ('Open Analytics', 'clean', {'type':'open_tool','tool':'analytics'}),
            ('Open Support', 'finance', {'type':'open_tool','tool':'support'}),
            ('Open Reports in Analytics', 'clean',
             {'type':'click_button','label':'Reports','tool':'analytics'}),
            ('Open Connections', 'analytics',
             {'type':'click_button','label':'Connections','tool':''}),
            ('Open Connections', 'preparePost',
             {'type':'click_button','label':'Connections','tool':''}),
            ('Open Editing clients', 'clean',
             {'type':'click_button','label':'Editing clients','tool':'aiAgents'}),
            ('Open Pocket Tracker', 'clean',
             {'type':'click_button','label':'Open Pocket Tracker','tool':'finance'}),
            ('Click Maximize call', 'finance',
             {'type':'click_button','label':'Expand call to fill screen','tool':'storylensCall'}),
        ]
        for sentence, active, expected in cases:
            with self.subTest(sentence=sentence, active=active), \
                 patch.object(local.speech,'transcribe',return_value=(sentence,'en')), \
                 patch.object(local,'gpu_lock'), patch.object(local,'_ollama_post') as model:
                result=local._answer(Path.cwd(),local.Call(),b'audio',active,'en',deferred=True)
                self.assertEqual(result['action'], expected)
                model.assert_not_called()

    def test_connections_help_is_scoped_to_the_named_workspace(self):
        from hinglish_app.support_call_controls import toolbar_help
        self.assertIn('supply analytics', toolbar_help('What does Connections do in Analytics?', 'preparePost'))
        self.assertIn('publishing account', toolbar_help('What does Connections do?', 'preparePost'))

    def test_action_response_does_not_wait_for_speech(self):
        with patch.object(local.speech,'transcribe',return_value=('Open Auto Caption','en')), \
             patch.object(local.speech,'synthesize') as synth, patch.object(local,'gpu_lock'):
            value=local._answer(Path.cwd(),local.Call(),b'audio','clean','en',deferred=True)
            self.assertTrue(value['speech_id'])
            self.assertEqual(value['audio'],'')
            self.assertEqual(value['action']['tool'],'captions')
            synth.assert_not_called()

    def test_open_it_uses_last_discussed_feature(self):
        call=local.Call()
        call.history.append({'role':'user','content':'What does Smart Visuals do?'})
        with patch.object(local.speech,'transcribe',return_value=('Open it','en')), \
             patch.object(local,'gpu_lock'):
            value=local._answer(Path.cwd(),call,b'audio','clean','en',deferred=True)
        self.assertEqual(value['action']['tool'],'visuals')


    def test_spoken_button_variants_keep_actual_label(self):
        from hinglish_app.support_call_controls import resolve_button_name
        snapshot=[('Choose videos', True, ''), ('Choose folder', True, ''), ('Output settings', True, '')]
        for spoken,wanted in [('Choose Video','Choose videos'),('select video','Choose videos'),
                              ('चूज़ वीडियो','Choose videos'),('फोल्डर चुनो','Choose folder')]:
            with self.subTest(spoken=spoken):
                self.assertEqual(resolve_button_name(spoken,'','broll',snapshot),wanted)

    def test_ambiguous_equivalences_are_not_guessed(self):
        from hinglish_app.support_call_controls import match_button_name
        self.assertEqual(match_button_name('select video',['Choose video','Choose videos']),'')
        self.assertEqual(match_button_name('Choose videos',['Choose video','Choose videos']),'Choose videos')
        self.assertEqual(match_button_name('delete',['Delete source','Delete output']),'')

    def test_real_failed_phrase_dispatches_actual_button_without_model(self):
        with patch.object(local.speech,'transcribe',return_value=('Click on Choose Video','en')), \
             patch.object(local.speech,'synthesize') as synth, patch.object(local,'gpu_lock'), \
             patch.object(local,'_ollama_post') as model:
            value=local._answer(Path.cwd(),local.Call(),b'audio','broll','en',
                               [('Choose videos',True,'')],deferred=True)
            self.assertEqual(value['action']['label'],'Choose videos')
            synth.assert_not_called()
            model.assert_not_called()

    def test_just_naming_visible_button_dispatches_it(self):
        with patch.object(local.speech,'transcribe',return_value=('Choose folder','en')), patch.object(local,'gpu_lock'):
            value=local._answer(Path.cwd(),local.Call(),b'audio','broll','en',
                               [('Choose folder',True,'')],deferred=True)
        self.assertEqual(value['action'],{'type':'click_button','label':'Choose folder','tool':''})

if __name__=='__main__': main()
