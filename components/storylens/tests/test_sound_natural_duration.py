import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from hinglish_sound.cues import place_cue
from hinglish_sound.layers import plan_layers, augment_moments


class Brain:
    def __init__(self, reply): self.reply=reply; self.calls=[]
    def ask(self, system, data, schema, **kw):
        self.calls.append((system,data,schema))
        return {'layers':self.reply(data) if callable(self.reply) else self.reply}


def layer(e, family, role, duration, intent):
    return dict(event_id=e,role=role,type=family,intent=intent,why='Supports this action',
                strength=2,offset=0.,duration=duration,level_db=-12.)


class NaturalDurationTests(unittest.TestCase):
    def test_invalid_continuous_duration_gets_one_model_authored_correction(self):
        event=dict(id='walk',time=0.,end=5.,kind='foley',precision='visual_interval',
                   label='Walking through mud',sound_evidence='Footsteps through mud')
        class CorrectingBrain(Brain):
            def ask(self,system,data,schema,**kw):
                self.calls.append((system,data,schema))
                if 'corrections' in schema['properties']:
                    return {'corrections':[dict(layer_index=0,duration=3.,duration_reason='Sustained sequence of muddy steps')]}
                return {'layers':[layer('walk','foley','detail',.1,'Footsteps through mud')]}
        brain=CorrectingBrain([])
        result=plan_layers(brain,[event],'Wet trail','emotional',1,['foley'],composition={'seconds':6})
        self.assertEqual(len(brain.calls),2)
        self.assertEqual(result[0]['duration'],3.)
        self.assertEqual(result[0]['intent'],'Footsteps through mud')
        self.assertEqual(result[0]['duration_correction'],'local model')

    def test_failed_duration_correction_is_bounded_and_does_not_stretch_audio(self):
        event=dict(id='walk',time=0.,end=5.,kind='foley',precision='visual_interval',label='Walking through mud')
        brain=Brain([layer('walk','foley','detail',.1,'Footsteps through mud')])
        result=plan_layers(brain,[event],'Wet trail','emotional',1,['foley'],composition={'seconds':6})
        self.assertEqual(result,[])
        self.assertEqual(len(brain.calls),2)

    def test_continuous_scene_rejects_word_sized_snippets_without_stretching(self):
        events=[dict(id='walk',time=0.,end=5.,kind='foley',precision='visual_interval',
                     label='Walking on muddy ground',sound_evidence='Footsteps through mud'),
                dict(id='water',time=0.,end=5.,kind='ambience',precision='sampled',label='Rushing water')]
        brain=Brain([layer('walk','foley','contact',.1,'Footsteps through muddy ground'),
                     layer('water','ambience','bed',.2,'Rushing river water')])
        result=plan_layers(brain,events,'Wet trail','emotional',2,['foley','ambience'],composition={'seconds':6})
        self.assertEqual(result,[])

    def test_scene_schema_binds_environment_and_action_to_their_own_events(self):
        events=[dict(id='walk',time=0.,end=5.,kind='foley',precision='visual_interval',label='Walking in mud'),
                dict(id='water',time=0.,end=5.,kind='ambience',precision='sampled',label='Rushing water')]
        brain=Brain([])
        plan_layers(brain,events,'Wet trail','emotional',2,['foley','ambience'],composition={'seconds':6})
        variants=brain.calls[0][2]['properties']['layers']['items']['anyOf']
        by_type={v['properties']['type']['enum'][0]:v['properties'] for v in variants}
        self.assertEqual(by_type['foley']['event_id']['enum'],['walk'])
        self.assertEqual(by_type['ambience']['event_id']['enum'],['water'])
        self.assertEqual(by_type['foley']['role']['enum'],['contact','detail'])
        self.assertEqual(by_type['ambience']['role']['enum'],['bed','texture'])
        self.assertGreaterEqual(by_type['ambience']['duration']['minimum'],1.)

    def test_short_observed_interval_can_remain_short(self):
        event=dict(id='water',time=0.,end=.3,kind='ambience',precision='sampled',label='Rushing water')
        brain=Brain([layer('water','ambience','bed',.3,'Rushing river water')])
        result=plan_layers(brain,[event],'Quick water cut','emotional',1,['ambience'],composition={'seconds':1})
        self.assertEqual(result[0]['duration'],.3)

    def test_authored_three_second_whoosh_is_not_cut_to_legacy_category_limit(self):
        asset=SimpleNamespace(path='sweep.wav',duration=4.,loudness=-20.,peak_time=.1)
        with patch('hinglish_sound.cues.exact_peak_time',return_value=.1), \
             patch('hinglish_sound.library.decode',return_value=np.ones((1,192000),np.float32)*.1):
            c=place_cue(asset,2.,'whoosh','Measured approach',requested_length=3.)
        self.assertAlmostEqual(c.length,3.)

    def test_short_source_is_never_stretched_to_fill_requested_duration(self):
        asset=SimpleNamespace(path='tap.wav',duration=.15,loudness=-20.,peak_time=.02)
        with patch('hinglish_sound.cues.exact_peak_time',return_value=.02), \
             patch('hinglish_sound.library.decode',return_value=np.ones((1,7200),np.float32)*.1):
            c=place_cue(asset,2.,'poke','A real click',requested_length=3.)
        self.assertAlmostEqual(c.length,.15)

    def test_physical_scene_has_budget_before_new_word_ticks(self):
        events=[dict(id='ride',time=1.,end=5.,kind='foley',precision='visual_interval',label='Rider moving on gravel')]
        words=[dict(id='word',time=1.,end=1.2,kind='speech',precision='speech',word='here',line_text='We are here')]
        def reply(data):
            e=data['events'][0]
            return [layer(e['id'],'foley' if e['kind']=='foley' else 'poke','detail',2.,
                          'gravel crunch under moving wheels' if e['kind']=='foley' else 'small dry click')]
        brain=Brain(reply)
        rows=augment_moments(brain,events,[],'A ride','comedic',1,['foley','poke'],
                             speech_events=words,composition={'seconds':8})
        self.assertEqual([r['source'] for r in rows],['foley'])
        self.assertEqual(brain.calls[0][1]['events'][0]['kind'],'foley')

    def test_roles_are_not_acoustic_search_descriptions(self):
        e=dict(id='w',time=2.,end=2.2,kind='speech',precision='speech',word='here')
        rows=plan_layers(Brain([layer('w','poke','detail',.1,'detail')]),[e],
                         'A reveal','comedic',1,['poke'],composition={'seconds':5})
        self.assertEqual(rows,[])

    def test_model_receives_natural_envelope_policy_and_keeps_three_second_sting(self):
        e=dict(id='w',time=2.,end=2.2,kind='speech',precision='speech',word='surprise')
        b=Brain([layer('w','cute','tail',3.,'warm playful descending musical chime')])
        rows=plan_layers(b,[e],'A joyful reveal','comedic',1,['cute','poke'],composition={'seconds':8})
        self.assertEqual(rows[0]['duration'],3.)
        guide=b.calls[0][1]['duration_guidance']
        self.assertIn('1–3',guide['developing_sounds'])
        self.assertIn('natural',guide['principle'])
        self.assertIn('duration_reason',b.calls[0][2]['properties']['layers']['items']['required'])
        self.assertIn('chime',b.calls[0][1]['sound_families']['cute'])
        self.assertIn('click',b.calls[0][1]['sound_families']['poke'])

    def test_water_recording_can_be_found_outside_ambience_folder(self):
        from hinglish_sound.retrieval import effect_candidates
        water=SimpleNamespace(path='water.wav',category='poke',duration=6.,name='Pool water lapping',text='Water lapping pool edge')
        horse=SimpleNamespace(path='horse.wav',category='foley',duration=6.,name='Horse galloping',text='Horse galloping')
        click=SimpleNamespace(path='click.wav',category='poke',duration=.1,name='Mouse click',text='Mouse click')
        index=SimpleNamespace(search=lambda query,**kw:[(a,1.,'') for a in (water,horse,click)] if kw['categories'] is None else [])
        hits,rejected=effect_candidates(index,'pool water',dict(type='ambience',intent='pool water lapping',duration=3.),(),())
        self.assertEqual([h[0].path for h in hits],['water.wav'])
        self.assertTrue(any(r['file']=='horse.wav' for r in rejected))

    def test_water_scene_cannot_author_fabric_or_wood_foley_from_prompt_examples(self):
        e=dict(id='slide',time=2.,end=6.,kind='foley',precision='visual_interval',
               label='Water flowing down a slide',sound_evidence='Visible water jets and moving water')
        rows=[layer('slide','foley','detail',3.,intent) for intent in
              ('dry fabric rubbing','dry wood sliding','water rushing over slide surface')]
        result=plan_layers(Brain(rows),[e],'A water park visit','comedic',1,['foley'],composition={'seconds':8})
        self.assertEqual([r['intent'] for r in result],['water rushing over slide surface'])

    def test_water_metadata_match_is_offered_even_when_vector_top_results_miss_it(self):
        from hinglish_sound.retrieval import effect_candidates
        water=SimpleNamespace(path='flow.wav',category='ambience',duration=51.,name='Water flowing ambience loop',text='natural water flowing')
        alien=SimpleNamespace(path='alien.wav',category='ambience',duration=8.,name='Alien drone',text='synthetic drone')
        index=SimpleNamespace(assets=[water,alien],search=lambda q,**kw:[(alien,1.,'')])
        rows,_=effect_candidates(index,'water and playful cinematic texture',dict(type='ambience',intent='water flowing',duration=5.),(),())
        self.assertEqual(rows[0][0].path,'flow.wav')

    def test_picker_schema_requires_every_moment_and_bounds_candidate_numbers(self):
        from hinglish_sound.director import pick
        calls=[]
        def ask(system,data,schema,**kw):
            calls.append(schema)
            return {'effects':[dict(moment=i,choice=0,why='Matching sound') for i in range(7)],'music':[]}
        b=SimpleNamespace(ask=ask)
        moments=[dict(line_text='A real line',word='here',type='cute',intent='resonant chime',emotion='joyful',duration=2.) for _ in range(7)]
        cands=[[{'doc':'a real matching chime'} for _ in range(6)] for _ in moments]
        with patch('hinglish_eval.tune.feedback',return_value=[]):pick(b,'A reveal','comedic',moments,cands,[],[],progress=lambda _:None)
        effects=calls[0]['properties']['effects']
        self.assertEqual(effects['minItems'],7)
        self.assertEqual(effects['maxItems'],7)
        self.assertEqual(effects['items']['properties']['choice']['enum'],[-1,0,1,2,3,4,5])

    def test_metadata_fallback_preserves_bans_and_tone_exclusions(self):
        from hinglish_sound.retrieval import effect_candidates
        assets=[SimpleNamespace(path=p,category='ambience',duration=9.,name='Water splashing',text='water')
                for p in ('banned.wav','cartoon.wav')]
        index=SimpleNamespace(assets=assets,genres=['neutral','funny'],search=lambda q,**kw:[])
        hits,_=effect_candidates(index,'water',dict(type='ambience',intent='water flowing',duration=3.),('funny',),('banned.wav',))
        self.assertEqual(hits,[])

    def test_heard_water_is_not_rejected_for_a_more_verbose_water_scene_intent(self):
        from hinglish_sound.evaluator import check_effect
        from hinglish_sound.listen import SFX_VOCAB
        names=list(SFX_VOCAB)
        def listener(best):
            scores=np.full(len(names)+1,.05);scores[names.index(best)]=.5;scores[-1]=.3
            return SimpleNamespace(similarity=lambda v,t:scores)
        good=check_effect(listener('water'),np.ones(2),{},'ambience','quiet water park ambience','comedic')
        self.assertTrue(good.passed)
        wrong=check_effect(listener('birds'),np.ones(2),{},'ambience','quiet water park ambience','comedic')
        self.assertFalse(wrong.passed)


if __name__=='__main__':unittest.main()
