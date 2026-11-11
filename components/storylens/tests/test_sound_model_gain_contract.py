import unittest
from hinglish_sound.layers import plan_layers

class ModelGainContractTests(unittest.TestCase):
    def test_model_can_choose_audible_primary_foley_without_double_attenuation(self):
        class Brain:
            def ask(self,system,data,schema,**kwargs):
                self.data=data
                return {'layers':[dict(event_id='ride',role='detail',type='foley',intent='Motorcycle engine running',why='Visible moving motorcycle',strength=2,offset=0.,duration=2.,target_level_db=-6.,duration_reason='Continuous riding',processing={})]}
        brain=Brain();event=dict(id='ride',kind='foley',time=0.,end=2.,precision='visual_interval',label='Motorcycle engine running')
        rows=plan_layers(brain,[event],'A motorcycle ride','emotional',1,['foley'],composition={'seconds':2})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['level_db'],4.)
        self.assertEqual(brain.data['mix_level_contract']['category_base_db']['foley'],-10.)
        self.assertEqual(brain.data['mix_level_contract']['default_speech_duck_db'],2.)
        self.assertEqual(rows[0]['target_level_db'],-6.)
        self.assertIn('final source level',brain.data['mix_level_contract']['meaning'])

if __name__=='__main__':unittest.main()
