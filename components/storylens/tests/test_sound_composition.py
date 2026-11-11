"""Behavioral contracts for dense, motivated speech-anchor sound ensembles."""
import math
import unittest

from hinglish_sound.cues import Cue
from hinglish_sound.layers import augment_moments, plan_layers, select_layers


FAMILIES=['impact','whoosh','riser','poke','cute','awkward','suspense','vanish','foley','ambience']


def anchor(i=0,time=2.,word='reveal',line_id=4):
    return dict(id=f'word-{line_id}-{i}',time=time,end=time+.2,kind='speech',precision='speech',
                word=word,word_index=i,line_id=line_id,line_text='A real spoken reveal is here',emotion='playful')


def layer(event_id,role='detail',family='poke',offset=0.,duration=.2,level_db=-6.):
    return dict(event_id=event_id,role=role,type=family,intent='soft clean tap',why='spoken emphasis',
                strength=2,offset=offset,duration=duration,level_db=level_db)


def base():
    return dict(id=4,type='impact',intent='short dry hit',target=2.,word='reveal',word_index=0,
                line_text='A real spoken reveal is here',strength=3,pull_back=True)


class Brain:
    def __init__(self,rows):self.rows=rows;self.calls=[]
    def ask(self,system,data,schema,**kwargs):
        self.calls.append((system,data,schema,kwargs))
        return {'layers':self.rows(data) if callable(self.rows) else self.rows}


class MotifBrain(Brain):
    def ask(self,system,data,schema,**kwargs):
        self.calls.append((system,data,schema,kwargs))
        return {'motifs':self.rows}


class SoundCompositionTests(unittest.TestCase):
    def test_base_accent_is_fixed_and_submitted_for_complementary_roles(self):
        brain=Brain([layer('speech-0','contact','impact'),
                     layer('speech-0','travel','whoosh',-.2,.3,-8),
                     layer('speech-0','tail','cute',.15,.4,-10)])
        rows=augment_moments(brain,[],[base()],'a joke lands','comedic',1,FAMILIES,
                             speech_events=[anchor()],composition={'seconds':5})
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['target'],2.)
        self.assertEqual(rows[0]['intent'],'short dry hit')
        self.assertTrue(rows[0]['pull_back'])
        self.assertEqual({r['group_id'] for r in rows},{'speech-0'})
        self.assertEqual([r['role'] for r in rows],['contact','travel','tail'])
        travel=rows[1]
        self.assertEqual(travel['anchor_time'],2.)
        self.assertEqual(travel['target'],1.8)
        self.assertEqual(travel['level_db'],-8)
        self.assertEqual(travel['word'],'reveal')
        self.assertIn('speech-0',[e['id'] for e in brain.calls[0][1]['events']])

    def test_additional_anchors_keep_exact_words_indices_and_measured_time(self):
        event=anchor(i=3,time=3.7,word='here')
        row=layer(event['id']);row.update(word='invented',word_index=99,target=99)
        result=augment_moments(Brain([row]),[],[],'spoken story','comedic',3,FAMILIES,
                               speech_events=[event],composition=True)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['word'],'here')
        self.assertEqual(result[0]['word_index'],3)
        self.assertEqual(result[0]['target'],3.7)
        self.assertEqual(result[0]['line_text'],event['line_text'])

    def test_existing_whoosh_reserves_travel_and_its_intent_is_visible_to_model(self):
        original=dict(base(),type='whoosh',intent='short soft air sweep')
        brain=Brain([layer('speech-0','travel','whoosh'),layer('speech-0','detail','poke')])
        rows=augment_moments(brain,[],[original],'story','comedic',1,FAMILIES,composition=True)
        self.assertEqual([r['role'] for r in rows],['travel','detail'])
        e=brain.calls[0][1]['events'][0]
        self.assertEqual(e['existing_accents'][0]['intent'],'short soft air sweep')
        self.assertEqual(e['existing_accents'][0]['type'],'whoosh')

    def test_anticipation_can_begin_before_anchor_but_not_before_video(self):
        e=anchor(time=.6)
        result=plan_layers(Brain([layer(e['id'],'anticipation','riser',-.4,.3,-12)]),
                           [e],'a reveal','comedic',1,FAMILIES,composition={'seconds':3})
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(result[0]['target'],.2)
        for bad in (-.8,-1.6,.1):
            self.assertEqual(plan_layers(Brain([layer(e['id'],'anticipation','riser',bad)]),
                             [e],'story','comedic',1,FAMILIES,composition={'seconds':3}),[])

    def test_invalid_model_fields_do_not_create_layers(self):
        e=anchor()
        bad=[]
        for field,values in {'offset':[float('nan'),float('inf'),'0',True,2.],
                             'duration':[None,-1.,0.,9.,float('nan'),True],
                             'level_db':['quiet',True,float('inf'),-25.,1.],
                             'intent':[None,[], 'Foley'], 'event_id':[[],{}]}.items():
            for value in values:
                bad.append(dict(layer(e['id']),**{field:value}))
        bad.append(layer('not-a-supplied-anchor'))
        self.assertEqual(plan_layers(Brain(bad),[e],'story','comedic',30,FAMILIES,composition=True),[])

    def test_five_nearby_supported_groups_and_five_role_ensemble_are_allowed(self):
        cues=[]
        for i,t in enumerate((1.,1.3,1.6,1.9,2.2)):
            cues.append(Cue(t,t,f'click-{i}.wav','poke',.18,-6,-20,'word',
                            source='speech',group_id=f'w{i}',role='detail',timing_precision='speech'))
        self.assertEqual(len(select_layers(cues,5,10,.65,composed=True)),5)
        self.assertLess(len(select_layers(cues,5,10,.65)),5)
        ensemble=[]
        for role,family in [('anticipation','riser'),('travel','whoosh'),('contact','impact'),
                            ('detail','poke'),('tail','cute')]:
            ensemble.append(Cue(2.,2.,role+'.wav',family,.5,-6,-20,'motivated ensemble',
                                source='speech',group_id='reveal',role=role))
        self.assertEqual(len(select_layers(ensemble,5,1,.65,composed=True)),5)
        self.assertEqual(len(select_layers(ensemble,5,1,.65)),3)
        ensemble.append(Cue(2.,2.,'extra.wav','poke',.5,-6,-20,'extra',group_id='another',role='detail'))
        self.assertEqual(len(select_layers(ensemble,5,2,.65,composed=True)),5)

    def test_composed_batches_have_compact_context_and_a_global_group_budget(self):
        events=[anchor(i=i,time=2+i*.1,word=f'w{i}') for i in range(120)]
        def choose(data):
            return [layer(e['id']) for e in data['events']]
        brain=Brain(choose)
        rows=augment_moments(brain,[],[],'a list','comedic',100,FAMILIES,
                             speech_events=events,composition=True)
        self.assertEqual(len(brain.calls),5)
        self.assertTrue(all(len(c[1]['events'])<=24 for c in brain.calls))
        self.assertTrue(all('line_text' not in e for c in brain.calls for e in c[1]['events']))
        self.assertTrue(all(len(c[1]['lines'])==1 for c in brain.calls))
        self.assertEqual(len({r['group_id'] for r in rows}),100)

    def test_speech_composition_schema_and_prompt_cannot_request_environmental_audio(self):
        brain=Brain([])
        augment_moments(brain,[],[],'a comic comparison','comedic',4,FAMILIES,
                        speech_events=[anchor()],composition=True)
        system,data,schema,_=brain.calls[0]
        self.assertNotIn('motifs',schema['properties'])
        item=schema['properties']['layers']['items']['properties']
        self.assertIn('intent',item)
        self.assertIn('offset',item)
        self.assertIn('reuse_reason',item)
        self.assertNotIn('foley',item['type']['enum'])
        self.assertNotIn('ambience',item['type']['enum'])
        self.assertNotIn('wind plus birds',system)
        self.assertNotIn('sustained Foley texture',system)
        self.assertIn('punctuation',system)
        self.assertIn('comic',system)
        self.assertEqual(data['lines'][0]['text'],anchor()['line_text'])

    def test_selected_motif_expands_to_multiple_valid_roles_at_fixed_anchor(self):
        brain=MotifBrain([dict(event_id=anchor()['id'],motif='graphic_reveal',why='a caption reveal',strength=2)])
        rows=augment_moments(brain,[],[],'graphic reveal','comedic',2,FAMILIES,
                             speech_events=[anchor()],composition=True)
        self.assertGreaterEqual(len(rows),3)
        self.assertEqual(len({r['role'] for r in rows}),len(rows))
        self.assertEqual({r['anchor_time'] for r in rows},{2.})
        self.assertEqual({r['group_id'] for r in rows},{anchor()['id']})
        self.assertEqual({r['word'] for r in rows},{'reveal'})

    def test_every_motif_compiles_only_valid_nonphysical_pairs_and_acoustic_intents(self):
        from hinglish_sound.layers import SPEECH_MOTIFS,ROLES
        for name in SPEECH_MOTIFS:
            with self.subTest(motif=name):
                brain=MotifBrain([dict(event_id=anchor()['id'],motif=name,why='motivated beat',strength=2)])
                rows=plan_layers(brain,[anchor()],'comic story','comedic',1,FAMILIES,composition=True)
                self.assertGreaterEqual(len(rows),2)
                for r in rows:
                    self.assertIn(r['type'],ROLES[r['role']])
                    self.assertNotIn(r['type'],('foley','ambience'))
                    self.assertNotIn(r['role'],('bed','texture'))
                    self.assertGreaterEqual(len(r['intent'].split()),3)
                    self.assertNotIn(r['intent'],list(ROLES)+list(SPEECH_MOTIFS))

    def test_two_list_motifs_can_have_six_starts_in_two_seconds(self):
        events=[anchor(i=0,time=1.,word='small'),anchor(i=1,time=1.35,word='medium')]
        brain=MotifBrain([dict(event_id=e['id'],motif='list_tick',why='spoken list item',strength=2) for e in events])
        rows=augment_moments(brain,[],[],'a list','comedic',2,FAMILIES,speech_events=events,composition=True)
        cues=[Cue(r['target'],r['target'],r['group_id']+r['role']+'.wav',r['type'],r['duration'],-6,-20,'list',
                  source='speech',group_id=r['group_id'],role=r['role'],timing_precision='speech') for r in rows]
        kept=select_layers(cues,5,2,.65,composed=True)
        self.assertEqual(len(kept),6)
        self.assertLess(max(c.time for c in kept)-min(c.time for c in kept),2.)
        self.assertLessEqual(max(sum(c.time<=t<c.time+c.length for c in kept) for t in [c.time for c in kept]),5)

    def test_foreign_motifs_or_anchor_ids_are_ignored_without_invented_layers(self):
        brain=MotifBrain([dict(event_id='foreign',motif='punchline',why='guess',strength=2),
                          dict(event_id=anchor()['id'],motif='invented',why='guess',strength=2),
                          dict(event_id=[],motif='list_tick',why='guess',strength=2)])
        self.assertEqual(plan_layers(brain,[anchor()],'story','comedic',3,FAMILIES,composition=True),[])

    def test_motif_preserves_reserved_base_role_and_unavailable_families_are_skipped(self):
        brain=MotifBrain([dict(event_id='speech-0',motif='punchline',why='a punchline',strength=3)])
        rows=augment_moments(brain,[],[base()],'comic turn','comedic',1,FAMILIES,
                             speech_events=[anchor()],composition=True)
        self.assertEqual(rows[0]['intent'],base()['intent'])
        self.assertEqual(rows[0]['target'],base()['target'])
        self.assertEqual(sum(r['role']=='contact' for r in rows),1)
        self.assertGreaterEqual(len(rows),3)
        sparse=plan_layers(MotifBrain([dict(event_id=anchor()['id'],motif='punchline',why='a turn',strength=2)]),
                           [anchor()],'story','comedic',1,['poke'],composition=True)
        self.assertTrue(sparse)
        self.assertEqual({r['type'] for r in sparse},{'poke'})

    def test_spoken_words_and_real_physical_actions_use_separate_model_calls(self):
        physical=dict(id='scrape',time=3.,end=4.,kind='foley',precision='visual_interval',
                      label='foreground brush repeatedly scrapes wood',uncertainty=.5)
        def choose(data):
            event=data['events'][0]
            return [layer(event['id'],'detail','foley' if event['kind']=='foley' else 'poke',0,
                          1. if event['kind']=='foley' else .2,-10)]
        brain=Brain(choose)
        rows=augment_moments(brain,[physical],[],'commentary with actual scrubbing','comedic',4,FAMILIES,
                             speech_events=[anchor()],composition=True)
        self.assertEqual(len(brain.calls),2)
        self.assertTrue(all(len({e['kind']=='speech' for e in call[1]['events']})==1 for call in brain.calls))
        self.assertEqual({r['source'] for r in rows},{'speech','foley'})
        physical_call=next(c for c in brain.calls if c[1]['events'][0]['kind']=='foley')
        self.assertIn('foley',physical_call[2]['properties']['layers']['items']['anyOf'][0]['properties']['type']['enum'])

    def test_global_budget_survives_the_speech_scene_split(self):
        physical=dict(id='scrape',time=3.,end=4.,kind='foley',precision='visual_interval',
                      label='foreground scraping',uncertainty=.5)
        def choose(data):
            return [layer(e['id'],'detail','foley' if e['kind']=='foley' else 'poke',0,
                          1. if e['kind']=='foley' else .2,-8)
                    for e in data['events']]
        result=augment_moments(Brain(choose),[physical],[base()],'story','comedic',2,FAMILIES,
                               speech_events=[anchor(),anchor(i=1,time=2.5,word='here')],composition=True)
        self.assertEqual(len({r['group_id'] for r in result if r['type']!='ambience'}),2)
        self.assertEqual(result[0]['target'],2.)

    def test_no_unmotivated_foley_or_forced_minimum_layers(self):
        e=anchor()
        self.assertEqual(augment_moments(Brain([]),[],[],'quiet words','serious',10,FAMILIES,
                                        speech_events=[e],composition=True),[])
        self.assertEqual(plan_layers(Brain([layer(e['id'],'detail','foley')]),[e],
                                     'a phone is mentioned','comedic',2,FAMILIES,composition=True),[])

    def test_legacy_augment_does_not_start_new_speech_planning_calls(self):
        brain=Brain([layer('speech-0')])
        rows=augment_moments(brain,[],[base()],'story','comedic',5,FAMILIES)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['target'],2.)
        self.assertEqual(brain.calls,[])

    def test_visual_interval_never_gets_an_invented_contact_offset(self):
        event=dict(id='scrape',time=2.,end=3.,kind='foley',precision='visual_interval',
                   label='visible sustained scraping',uncertainty=.5)
        result=plan_layers(Brain([layer('scrape','detail','foley',.15,.5,-12)]),[event],
                           'scrape','serious',2,FAMILIES,composition=True)
        self.assertEqual(result,[])

    def test_complementary_layers_reserve_space_for_later_base_accents(self):
        ensemble=[]
        for role,family in [('contact','impact'),('anticipation','riser'),('travel','whoosh'),
                            ('detail','poke'),('tail','cute')]:
            ensemble.append(Cue(1.,1.,role+'.wav',family,1.,-6,-20,'ensemble',
                            source='ai' if role=='contact' else 'speech',group_id='first',role=role,
                            timing_precision='speech'))
        later=Cue(1.2,1.2,'base-two.wav','impact',.3,-6,-20,'another exact word',
                  source='ai',group_id='second',role='contact',timing_precision='speech')
        kept=select_layers(ensemble+[later],5,2,.65,composed=True)
        self.assertIn(later,kept)
        self.assertIn(ensemble[0],kept)
        self.assertEqual(len(kept),5)


if __name__=='__main__':unittest.main()
