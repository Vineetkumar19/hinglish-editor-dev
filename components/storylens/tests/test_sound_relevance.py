"""Regressions from the owner's rejected nightlife soundtrack."""
import unittest
import numpy as np
from hinglish_sound.evaluator import check_effect
from hinglish_sound.listen import SFX_VOCAB
from hinglish_sound.layers import plan_layers, scene_events


class SoundRelevanceTests(unittest.TestCase):
    def test_designed_accent_accepts_primary_family_despite_prompt_score_variance(self):
        class Listener:
            def similarity(self, vector, texts):
                scores=np.full(len(texts), .05)
                scores[list(SFX_VOCAB).index('whoosh')]=.55
                scores[-1]=.43
                return scores
        self.assertTrue(check_effect(Listener(),np.ones(2),{},'whoosh','subtle whoosh','serious').passed)

    def test_trigger_type_repair_also_repairs_incompatible_sound_intent(self):
        from hinglish_sound.director import validate_moments
        from types import SimpleNamespace
        analysis={'moments':[dict(id=0,trigger='new_place_or_time_jump',evidence='ten baje ke baad',
                                  type='impact',intent='low cinematic boom',word='baad')]}
        kept,_=validate_moments(analysis,[SimpleNamespace(id=0,text='ten baje ke baad')],['whoosh'],'serious')
        self.assertEqual(kept[0]['type'],'whoosh')
        self.assertIn('whoosh',kept[0]['intent'])
        self.assertNotIn('boom',kept[0]['intent'])
        # Model repair can change the type but leave its old incompatible query.
        analysis['moments'][0]['type']='whoosh'
        kept,_=validate_moments(analysis,[SimpleNamespace(id=0,text='ten baje ke baad')],['whoosh'],'serious')
        self.assertIn('whoosh',kept[0]['intent'])

    def test_broad_foley_match_cannot_pass_unrelated_footsteps(self):
        class Listener:
            def similarity(self, vector, texts):
                scores=np.full(len(texts), .05)
                scores[list(SFX_VOCAB).index('footsteps')]=.55
                scores[list(SFX_VOCAB).index('cloth')]=.15
                scores[-1]=.12
                return scores
        result=check_effect(Listener(),np.ones(2),{},'foley','quiet fabric rubbing','comedic')
        self.assertFalse(result.passed)

    def test_generic_family_is_not_a_sound_description(self):
        class Brain:
            def ask(self,*args,**kwargs):
                return {'layers':[dict(event_id='action',role='detail',type='foley',
                    intent='Foley',why='Fabric rustles',strength=1)]}
        events=[dict(id='action',time=1,end=2,kind='foley',label='rubbing cloth',precision='visual_interval')]
        self.assertEqual(plan_layers(Brain(),events,'story','comedic',2,['foley']),[])

    def test_incidental_pose_and_unspecified_sound_evidence_are_not_events(self):
        events=[dict(frame=0,end_frame=1,action='holds a phone',confidence=.98,
                     action_kind='incidental_pose',sound_evidence=''),
                dict(frame=0,end_frame=1,action='looks down',confidence=.98),
                dict(frame=0,end_frame=1,action='scrubs rough wood',confidence=.98,
                     action_kind='continuous_physical_action',sound_evidence='Brush visibly scrapes wood repeatedly')]
        result=scene_events({'events':events},[0,.5],1)
        self.assertEqual([r['label'] for r in result],['scrubs rough wood'])

    def test_layer_plan_keeps_spoken_accents_even_when_model_returns_no_layers(self):
        from hinglish_sound.layers import augment_moments
        class Brain:
            def ask(self,*args,**kwargs): return {'layers':[]}
        base=[dict(type='awkward',intent='brief record scratch',target=4.22,
                   word='nahi',word_index=3,pull_back=True,line_text='par nahi',strength=2)]
        result=augment_moments(Brain(),[],base,'dry comedy','comedic',3,['awkward'])
        self.assertEqual(len(result),1)
        for key in base[0]: self.assertEqual(result[0][key],base[0][key])
        self.assertEqual(result[0]['timing_precision'],'speech')
        self.assertEqual(result[0]['group_id'],'speech-0')

    def test_candidate_description_keeps_actual_identity_before_classifier_guesses(self):
        from hinglish_sound.vectors import document
        from hinglish_sound.library import Asset
        asset=Asset('foot.wav','sfx','foley','Footsteps on heels on pavement',
                    'footsteps walking pavement heels',2,-20,.1)
        doc=document(asset,{'sounds_like':['record scratch','heartbeat','footsteps']})
        self.assertIn(asset.name,doc[:260])


if __name__=='__main__': unittest.main()
