"""Exact speech anchors and additive role mix from a composed soundtrack."""
from pathlib import Path
from types import SimpleNamespace
import tempfile,unittest
import numpy as np
from hinglish_sound.cues import Cue
from hinglish_sound.mix import mix,write_wav,body_db

class AnchorCompositionTests(unittest.TestCase):
    def test_library_queries_are_warmed_in_one_batch_without_changing_text(self):
        from hinglish_sound.composition import warm_queries
        class Brain:
            def __init__(self):self.calls=[]
            def embed(self,texts):self.calls.append(texts)
        brain=Brain()
        warm_queries(brain,['short pop. comedic','short tick. playful','short pop. comedic'],['neutral comedic instrumental'])
        self.assertEqual(brain.calls,[['short pop. comedic','short tick. playful','neutral comedic instrumental']])

    def test_empty_ambience_observations_cannot_create_sound_events(self):
        from hinglish_sound.composition import ambience_events
        observations=[dict(time=i,end=i+1,confidence=.95,ambience=text)
                      for i,text in enumerate(['Empty','Empty for indoor talking-head footage.','None','quiet indoor room tone','Noisy street traffic'])]
        rows=ambience_events(observations,6)
        self.assertEqual([r['label'] for r in rows],['quiet indoor room tone','Noisy street traffic'])

    def test_repeated_intents_still_receive_each_distinct_line_context(self):
        from hinglish_sound.director import pick
        class Brain:
            def __init__(self):self.selections=0
            def ask(self,system,data,schema,**kwargs):
                self.selections+=len(data['moments'])
                return {'effects':[dict(moment=m['moment'],choice=0,why='same short click palette') for m in data['moments']],'music':[]}
        brain=Brain()
        moments=[dict(type='poke',intent='short clean click',emotion='playful',role='detail',
                      line_text=f'List item {i}',word=f'item{i}',group_id=str(i)) for i in range(10)]
        result=pick(brain,'a list','comedic',moments,[[{'doc':'same real click'}] for _ in moments],[],[],progress=lambda x:None)
        self.assertEqual([r['moment'] for r in result['effects']],list(range(10)))
        self.assertTrue(all(r['choice']==0 for r in result['effects']))
        self.assertEqual(brain.selections,10)

    def test_composed_story_pass_leaves_effect_authoring_to_measured_anchor_composer(self):
        from hinglish_sound.director import analyse
        class Brain:
            def ask(self,system,data,schema,**kwargs):
                self.schema=schema;self.data=data
                return dict(story='A dry comic setup',palette='comedic',
                            lines=[dict(id=0,emotion='mock shock',intensity=2,role='hook')],music=[],moments=[])
        brain=Brain()
        result=analyse(brain,'short video',[SimpleNamespace(id=0,start=0,end=1,text='Nightlife? Really?')],[],[],[],['poke'],
                       count=8,progress=lambda x:None,composition={'seconds':1})
        self.assertEqual(brain.schema['properties']['moments']['maxItems'],0)
        self.assertEqual(result['moments'],[])
        self.assertIn('mock shock',result['lines'][0]['emotion'])

    def test_composed_palette_is_reviewed_with_rhetorical_delivery_and_reference(self):
        from hinglish_sound.composition import rhetorical_palette
        class Brain:
            def ask(self,system,data,schema,**kwargs):
                self.data=data
                return dict(palette='comedic',reason='Dry mock-serious comedy, not a literal threat.')
        brain=Brain()
        analysis=dict(story='Dry observational comedy about empty nightlife',palette='serious',
                      lines=[dict(id=0,emotion='mock shocked',role='hook')])
        result=rhetorical_palette(brain,analysis,'auto',{'reference_name':'Owner edit'},
                                 [{'time':0,'mood':'dry, playful','action':'speaking'}])
        self.assertEqual(result['palette'],'comedic')
        self.assertEqual(brain.data['initial_palette'],'serious')
        self.assertEqual(brain.data['delivery'][0]['emotion'],'mock shocked')
        self.assertEqual(brain.data['reference']['reference_name'],'Owner edit')
        self.assertEqual(brain.data['visual_moods'][0]['mood'],'dry, playful')

    def test_explicit_palette_keeps_owner_choice_without_another_model_call(self):
        from hinglish_sound.composition import rhetorical_palette
        class Brain:
            def ask(self,*args,**kwargs):raise AssertionError('Owner-selected style must win')
        self.assertEqual(rhetorical_palette(Brain(),{'palette':'comedic'},'cinematic',{'seconds':4})['palette'],'serious')

    def test_intentionally_quiet_tail_is_not_reported_as_failed_but_silence_is(self):
        from hinglish_sound.evaluator import mix_qa
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);t=np.arange(96000)/48000
            voice=(.1*np.sin(t*220*2*np.pi)).astype(np.float32)
            source=write_wav(folder/'tail.wav',(.1*np.sin(t[:24000]*7000*2*np.pi)).astype(np.float32))
            c=Cue(.5,.5,str(source),'cute',.5,-28,-20,'quiet tail',group_id='word',role='tail')
            result=mix(voice,[],[c],folder,layered=True,composed=True)
            args=(voice,None,result['effects'],result['master'],result['speech'],[c],1,.65)
            qa=mix_qa(*args,layered=True,composed=True)
            self.assertTrue(qa[0]['passed'],qa[0])
            silent=[(24000,np.zeros_like(result['effects'][0][1]),c)]
            qa=mix_qa(voice,None,silent,result['master'],result['speech'],[c],1,.65,layered=True,composed=True)
            self.assertFalse(qa[0]['passed'])

    def test_legitimate_close_anchors_pass_both_mix_and_export_spacing(self):
        from hinglish_sound.evaluator import mix_qa
        from hinglish_eval.specs import sound_checks
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);t=np.arange(48000)/48000
            source=write_wav(folder/'accent.wav',(.1*np.sin(t[:6000]*600*2*np.pi)).astype(np.float32))
            rows=[Cue(.1+i*.04,.1+i*.04,str(source),'poke',.125,-10,-20,'test',group_id=f'word-{i}',role='detail') for i in range(3)]
            result=mix(np.zeros(48000,np.float32),[],rows,folder,layered=True,composed=True)
            plan=dict(settings={'layered':True,'music':False},composition_version=2,cues=[c.to_dict() for c in rows],
                      stems=result['stems'],words_db=result['words_db'],voice_peak=result['voice_peak'],
                      words_full_db=result['words_full_db'],lines=[{'end':1}],budget=3,gap=.65)
            checks={c.rule:c for c in sound_checks(folder,plan)}
            self.assertTrue(checks['sound.spacing'].passed,checks['sound.spacing'].value)
            qa=mix_qa(np.zeros(48000,np.float32),None,result['effects'],result['master'],result['speech'],rows,3,.65,layered=True,composed=True)
            self.assertTrue(next(q['passed'] for q in qa if 'Spacing' in q['check']))

    def test_speech_anchors_preserve_words_occurrences_and_base_identity(self):
        from hinglish_sound.composition import speech_events
        lines=[SimpleNamespace(id=4,start=0,end=2,text='No club, no lounge')]
        words=[SimpleNamespace(start=a,end=a+.2,text=w) for a,w in [(0,'No'),(.4,'club,'),(.8,'no'),(1.2,'lounge')]]
        base=[dict(target=.8,word='no',word_index=2,line_text=lines[0].text)]
        events=speech_events(lines,words,base)
        self.assertEqual(len(events),4)
        self.assertEqual([r['time'] for r in events],[0,.4,.8,1.2])
        self.assertEqual([r['word'] for r in events],['No','club,','no','lounge'])
        self.assertEqual(events[2]['id'],'speech-0')
        self.assertEqual(events[2]['word_index'],2)

    def test_composed_mix_does_not_blanket_attenuate_a_complete_ensemble(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);t=np.arange(48000)/48000
            source=write_wav(folder/'accent.wav',(.1*np.sin(t*600*2*np.pi)).astype(np.float32))
            rows=[Cue(0,0,str(source),'poke',1,-10,-20,'test',group_id='ensemble',role=role)
                  for role in ('contact','travel','detail')]
            result=mix(np.zeros(96000,np.float32),[],rows,folder,layered=True,composed=True)
            self.assertEqual([s['layer_trim_db'] for s in result['stems']['effects']],[0,0,0])
            self.assertTrue(np.isfinite(result['master']).all())
            self.assertLess(np.max(np.abs(result['master'])),1)

    def test_old_layered_mix_keeps_its_previous_gain_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);t=np.arange(48000)/48000
            source=write_wav(folder/'accent.wav',(.1*np.sin(t*600*2*np.pi)).astype(np.float32))
            rows=[Cue(0,0,str(source),'poke',1,-10,-20,'test',group_id='ensemble',role=role)
                  for role in ('contact','travel','detail')]
            result=mix(np.zeros(96000,np.float32),[],rows,folder,layered=True)
            self.assertTrue(all(abs(s['layer_trim_db']+10*np.log10(3))<1e-6 for s in result['stems']['effects']))

if __name__=='__main__':unittest.main()
