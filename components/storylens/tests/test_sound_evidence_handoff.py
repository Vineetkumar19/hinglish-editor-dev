import unittest
from hinglish_sound.events import normalize
from hinglish_sound.composition import ambience_events
from hinglish_sound.layers import plan_layers

class EvidenceHandoffTests(unittest.TestCase):
 def test_physical_mechanism_reaches_composer_and_relevance_filter(self):
  events=normalize([dict(time=0,end=2,kind='foley',label='riding',precision='visual_interval',confidence=.9,sound_evidence='Motorcycle engine running; tires rolling on wet mud')],2)
  class Brain:
   def ask(self,system,data,schema,**kwargs):
    self.data=data
    return {'layers':[dict(event_id=events[0]['id'],role='detail',type='foley',intent='Motorcycle engine running',why='Observed motorcycle',strength=2,offset=0,duration=2,target_level_db=-8)]}
  brain=Brain();rows=plan_layers(brain,events,'Travel','calm',1,['foley'],composition={'seconds':2})
  self.assertEqual(events[0]['sound_evidence'],'Motorcycle engine running; tires rolling on wet mud')
  self.assertEqual(brain.data['events'][0]['sound_evidence'],events[0]['sound_evidence'])
  self.assertEqual(len(rows),1,'Do not reject an engine after losing its visual evidence')

 def test_waterfall_identity_is_not_lost_in_generic_water_ambience(self):
  obs=[dict(time=2,end=5,confidence=.95,setting='Forest waterfall',action='Water cascading over rocks',ambience='Continuous rushing water')]
  event=normalize(ambience_events(obs,5),5)[0]
  self.assertIn('waterfall',event['sound_evidence'].lower())
  self.assertIn('cascading',event['sound_evidence'])
  self.assertEqual(event['confidence'],.95)

if __name__=='__main__':unittest.main()
