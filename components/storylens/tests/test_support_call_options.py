import base64
import json
from pathlib import Path
from time import perf_counter
import unittest
from unittest.mock import patch

from hinglish_app.support_call_actions import interpret
from hinglish_app.support_call_controls import decode_fields, option_command, select_fields
from hinglish_app.support_call_router import routing_context

class VoiceOptionRoutingTests(unittest.TestCase):
    def test_real_motion_options_and_natural_commands(self):
        choices = next(row for row in select_fields('motion') if row['id'] == 'motionEngine')
        self.assertEqual([row['value'] for row in choices['options']], ['remotion','motion-canvas','hyperframes'])
        for text in ('hyper frame kar de', 'hyper frame कर दे', 'Hyperframes',
                     'Please select Hyperframes', 'Set Render engine to hyper frame'):
            with self.subTest(text=text):
                action = option_command(text,'motion')
                self.assertEqual(action['field_id'],'motionEngine')
                self.assertEqual(action['value'],'hyperframes')

    def test_actual_joined_hindi_asr_imperatives_are_grounded(self):
        for text in ('Hyperframe करदे।', 'Hyperframe करदो', 'Hyperframe करदीजिए',
                     'Hyperframe कर दीजिए'):
            with self.subTest(text=text):
                action = option_command(text, 'motion')
                self.assertEqual(action['value'], 'hyperframes')
                self.assertEqual(action['field_id'], 'motionEngine')
        self.assertIsNone(option_command('Hyperframe Card', 'motion'))
        self.assertIsNone(option_command('Unknown option करदे', 'motion'))
        self.assertIsNone(option_command('Hyperframe नहीं करदे', 'motion'))

    def test_explicit_other_feature_is_scoped(self):
        action=option_command('Use Hyperframes in render engine in Motion Graphics','broll')
        self.assertEqual(action['tool'],'motion')
        self.assertEqual(action['value'],'hyperframes')
        self.assertIsNone(option_command('Use Hyperframes in Motion Graphics and Auto Captions','broll'))

    def test_live_dynamic_options_are_used_and_disabled_static_is_not_restored(self):
        live=[{'id':'motionEngine','label':'Render engine','disabled':False,
               'options':[{'value':'new-engine','label':'New Engine','disabled':False}]}]
        self.assertEqual(option_command('select New Engine','motion',live)['value'],'new-engine')
        self.assertIsNone(option_command('select Hyperframes','motion',live))
        live[0]['disabled']=True
        self.assertIsNone(option_command('select New Engine','motion',live))

    def test_negation_questions_quotes_and_ambiguity_never_execute(self):
        for text in ('What is Hyperframes?', 'How do I select Hyperframes?',
                     'Do not use Hyperframes', "Don't use Hyperframes", 'Hyperframes मत चुनो',
                     'I like Hyperframes', 'If I select Hyperframes', '"select Hyperframes"',
                     'select full'):
            with self.subTest(text=text):
                self.assertIsNone(option_command(text,'motion'))
        rows=[{'id':'first','label':'First menu','options':[{'value':'unique','label':'Unique'}]},
              {'id':'second','label':'Second menu','options':[{'value':'unique','label':'Unique'}]}]
        self.assertIsNone(option_command('select unique','motion',rows))
        self.assertEqual(option_command('select unique in First menu','motion',rows)['field_id'],'first')

    def test_metadata_bounds_and_no_text_values(self):
        raw=[{'id':'engine','label':'Render engine','value':'SECRET_CURRENT_VALUE',
              'options':[{'value':'hyperframes','label':'Hyperframes','disabled':False}]}]
        rows=decode_fields(base64.b64encode(json.dumps(raw).encode()).decode())
        self.assertNotIn('SECRET_CURRENT_VALUE',repr(rows))
        self.assertEqual(len(rows),1)
        self.assertEqual(decode_fields('x'*12001),())
        self.assertEqual(decode_fields('invalid'),())

    def test_broll_navigation_paraphrases_do_not_call_desktop(self):
        with patch('hinglish_app.support_call_actions._worker') as worker:
            for text in ('Open B roll', 'Open B-roll', 'Open bee roll',
                         'Can we head over to B-roll?', 'Could you bring me to the B-roll screen?'):
                with self.subTest(text=text):
                    outcome=interpret(Path.cwd(),text,'en','clean')
                    self.assertEqual(outcome.action,{'type':'open_tool','tool':'broll'})
            worker.assert_not_called()

    def test_router_receives_options(self):
        context=routing_context('Use Hyperframes','motion',(),())
        self.assertIn('Render engine',context)
        self.assertIn('hyperframes',context)

    def test_warm_deterministic_dispatch_is_bounded_without_model(self):
        option_command('Hyperframes','motion')
        start=perf_counter()
        for _ in range(100):
            self.assertEqual(option_command('hyper frame kar de','motion')['value'],'hyperframes')
        # This is only CPU routing latency, not microphone-to-audio latency.
        self.assertLess(perf_counter()-start,1.0)

if __name__=='__main__':
    unittest.main()
