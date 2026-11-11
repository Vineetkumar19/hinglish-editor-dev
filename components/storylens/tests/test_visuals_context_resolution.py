"""Recorded negative housing case plus labelled CPU disambiguation fixtures.

No model/search calls. Positive typed replies below exercise the controller only;
they are not substituted into production and are not semantic acceptance.
"""
import copy
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hinglish_visuals.web import Entity


# Exact candidates from the preserved PG search response for engine 4666cad90fe1.
PG_RESULTS = [
    {'id':'Q18665334','label':'PG','description':'film content classification given by the Motion Picture Association','matched_name':'PG'},
    {'id':'Q691','label':'Papua New Guinea','description':'country in Oceania','matched_name':'pg'},
    {'id':'Q26708076','label':'PG','description':'Australian Classification media rating: parental guidance recommended','matched_name':'PG'},
    {'id':'Q2612219','label':'petagram','description':'unit of mass, equal to 10¹⁵ grams','matched_name':'Pg'},
    {'id':'Q74434526','label':'PG','description':'theatrical certificate in the IFCO classification system','matched_name':'PG'},
    {'id':'Q22673','label':'Project Gutenberg','description':'free digital library','matched_name':'PG'},
]


class Brain:
    def __init__(self, **reply):
        self.reply=reply;self.calls=[]
    def json(self,system,data,schema,**kwargs):
        self.calls.append((system,copy.deepcopy(data),schema,kwargs))
        return copy.deepcopy(self.reply)


class Web:
    def __init__(self,results):self.results=results;self.fetched=[]
    def search_entities(self,name):return copy.deepcopy(self.results)
    def entity(self,key,name,kind,qid):
        self.fetched.append(qid)
        row=next(r for r in self.results if r['id']==qid)
        return Entity(key,name,kind,qid,label=row['label'],description=row['description'])


class ContextResolutionTests(unittest.TestCase):
    def context(self,meaning='The creator is currently staying in a PG (paying guest) accommodation.',category='room'):
        return {'country':'India','moments':[{'quote':'PG mein','mention':'PG','meaning':meaning,
                    'visual':'A typical PG room in North India','category':category}],
                'speech':[{'id':3,'text':'To main kahaan ruka hoon? PG mein.'}],
                'story':['Struggles of finding a flat for a bachelor in North India']}

    def reply(self,**changes):
        return {'id':'Q22673','referent':'named','compatible':True,'constraints_match':True,
                'reason':'Synthetic controller fixture',**changes}

    def test_recorded_housing_pg_cannot_adopt_gutenberg_even_if_reply_picks_it(self):
        from hinglish_visuals.planner import resolve_entity
        brain=Brain(**self.reply());web=Web(PG_RESULTS)
        found=resolve_entity(brain,web,{'key':'pg','name':'PG','kind':'place','about':'paying guest accommodation'},
            {'country':'India','topic':'Struggles of finding a flat for a bachelor in North India'},
            resolution_context=self.context())
        self.assertIsNone(found)
        self.assertEqual(web.fetched,[])

    def test_pg_library_context_still_permits_real_library_identity(self):
        from hinglish_visuals.planner import resolve_entity
        brain=Brain(**self.reply());web=Web(PG_RESULTS)
        outcome={}
        found=resolve_entity(brain,web,{'key':'pg','name':'PG','kind':'thing','about':'digital ebook library'},
            {'country':'India','topic':'Reading public-domain ebooks'},
            resolution_context=self.context('The creator downloads ebooks from PG.','digital library'),resolution_outcome=outcome)
        self.assertEqual(found.qid,'Q22673')
        self.assertEqual(found.name,'PG')
        self.assertEqual(found.label,'Project Gutenberg')
        self.assertEqual((outcome['status'],outcome['referent']),('resolved','named'))
        self.assertFalse(outcome['needs_clarification'])

    def test_ambiguous_and_generic_class_are_not_invented_exact_places(self):
        from hinglish_visuals.planner import resolve_entity
        for referent in ('generic','ambiguous'):
            brain=Brain(**self.reply(id='Q188507',referent=referent))
            web=Web([{'id':'Q188507','label':'apartment','description':'self-contained housing unit occupying part of a building','matched_name':'flat'}])
            found=resolve_entity(brain,web,{'key':'flat','name':'Flat','kind':'place','about':'accommodation'},
                {'country':'India','topic':'Finding a flat'},resolution_context=self.context('Looking for a flat.','room'))
            self.assertIsNone(found);self.assertEqual(web.fetched,[])

    def test_context_boolean_and_membership_checks_cannot_be_truthy_strings(self):
        from hinglish_visuals.planner import resolve_entity
        row={'id':'Q_BUILDING','label':'Named Guest House','description':'residential building in Bengaluru, India'}
        for change in ({'compatible':'false'},{'constraints_match':'true'},{'compatible':False},
                       {'constraints_match':False},{'id':'Q_foreign'},{'referent':'unknown'}):
            brain=Brain(**self.reply(id='Q_BUILDING',**({k:v for k,v in change.items() if k!='id'})))
            if 'id' in change:brain.reply['id']=change['id']
            web=Web([row])
            with self.subTest(change=change):
                self.assertIsNone(resolve_entity(brain,web,{'key':'home','name':'Guest House','kind':'place','about':'named accommodation'},
                    {'country':'India'},resolution_context=self.context(category='building')))
                self.assertEqual(web.fetched,[])

    def test_actual_context_full_constraints_and_boolean_think_reach_model(self):
        from hinglish_visuals.planner import resolve_entity
        summary={'country':'India','topic':'Visiting a named building','source_constraints':{'city':'Bengaluru'},
                 'creator_guidance_sentinel':{'keep_full':['first','last']}}
        context=self.context(category='building');original=copy.deepcopy((summary,context))
        brain=Brain(**self.reply(id='Q_BUILDING'))
        web=Web([{'id':'Q_BUILDING','label':'Named Guest House','description':'residential building in Bengaluru, India'}])
        found=resolve_entity(brain,web,{'key':'home','name':'Guest House','kind':'place','about':'named accommodation'},
                             summary,resolution_context=context)
        self.assertEqual(found.qid,'Q_BUILDING')
        _,data,schema,kwargs=brain.calls[-1]
        self.assertEqual(data['video_context'],summary)
        self.assertEqual(data['resolution_context'],context)
        self.assertIs(kwargs['think'],False)
        self.assertEqual(schema['properties']['compatible']['type'],'boolean')
        self.assertEqual((summary,context),original)

    def test_pipeline_passes_quotes_neighbors_and_keeps_generic_name_and_anchors(self):
        from hinglish_visuals.pipeline import resolve_visual_entity
        from hinglish_visuals.planner import VisualMoment
        phrase=SimpleNamespace(id=1,start=2.,end=4.,text='To main kahaan ruka hoon? PG mein.')
        neighbour=SimpleNamespace(id=0,start=0.,end=2.,text='Finding a flat is difficult.')
        moment=VisualMoment(1,'A typical PG room',['PG accommodation in India'],2,'PG mein',
                            'Staying in paying guest accommodation','pg','PG','photo','popup',category='room')
        before=copy.deepcopy(moment)
        spec={'key':'pg','name':'PG','kind':'place','about':'paying guest accommodation'}
        with patch('hinglish_visuals.pipeline.resolve_entity',return_value=None) as resolve:
            result=resolve_visual_entity(None,None,spec,{'country':'India'},[moment],[neighbour,phrase],
                                         ['Housing story'],script='',review_options=True,progress=lambda _:None)
        self.assertEqual(result.name,'PG');self.assertEqual(result.label,'PG');self.assertFalse(result.qid)
        self.assertEqual(moment,before)
        context=resolve.call_args.kwargs['resolution_context']
        self.assertEqual(context['country'],'India')
        self.assertEqual([p['text'] for p in context['speech']],[neighbour.text,phrase.text])
        self.assertEqual(context['moments'][0]['quote'],'PG mein')

    def test_canonical_rewriting_requires_acceptance_and_preserves_spoken_identity(self):
        from hinglish_visuals.planner import apply_canonical_name,VisualMoment
        moment=VisualMoment(1,'PG library',['PG ebooks'],2,'PG se','Download ebooks','pg','PG','photo','popup')
        spec={'key':'pg','name':'PG'}
        entity=Entity('pg','PG','thing','Q22673',label='Project Gutenberg')
        before=copy.deepcopy(moment)
        apply_canonical_name(spec,entity,[moment],compatible=False)
        self.assertEqual(moment,before)
        apply_canonical_name(spec,entity,[moment],compatible=True)
        self.assertEqual(moment.visual,'Project Gutenberg library')
        self.assertEqual(moment.queries,['Project Gutenberg ebooks'])
        self.assertEqual((moment.quote,moment.mention,moment.phrase_id),(before.quote,before.mention,before.phrase_id))
        self.assertEqual(entity.name,'PG')

    def test_legacy_call_without_context_keeps_its_existing_contract(self):
        from hinglish_visuals.planner import resolve_entity
        brain=Brain(id='Q22673');web=Web(PG_RESULTS)
        found=resolve_entity(brain,web,{'key':'pg','name':'PG','kind':'thing','about':'digital library'}, {'topic':'ebooks'})
        self.assertEqual(found.qid,'Q22673')
        self.assertNotIn('resolution_context',brain.calls[-1][1])

    def test_bare_pg_preserves_typed_ambiguity_and_plain_question(self):
        from hinglish_visuals.planner import resolve_entity
        outcome={}
        bare={'country':'','moments':[{'quote':'PG','mention':'PG','meaning':'PG','category':''}],
              'speech':[{'id':0,'text':'PG'}],'story':[]}
        result=resolve_entity(Brain(**self.reply(id='',referent='ambiguous',compatible=False)),Web(PG_RESULTS),
            {'key':'pg','name':'PG','kind':'place','about':''},{'topic':''},
            resolution_context=bare,resolution_outcome=outcome)
        self.assertIsNone(result)
        self.assertEqual(outcome['referent'],'ambiguous')
        self.assertEqual(outcome['status'],'needs_clarification')
        self.assertEqual(outcome['quoted_words'],['PG'])
        self.assertTrue(outcome['needs_clarification'])
        self.assertIn('PG',outcome['clarification_question'])
        self.assertTrue(outcome['clarification_question'].endswith('?'))

    def test_known_housing_meaning_stays_generic_without_redundant_question(self):
        from hinglish_visuals.planner import resolve_entity
        outcome={}
        result=resolve_entity(Brain(**self.reply()),Web(PG_RESULTS),
            {'key':'pg','name':'PG','kind':'place','about':'paying guest accommodation'},
            {'country':'India','topic':'Finding housing'},resolution_context=self.context(),resolution_outcome=outcome)
        self.assertIsNone(result)
        self.assertEqual(outcome['status'],'generic')
        self.assertEqual(outcome['referent'],'generic')
        self.assertFalse(outcome['needs_clarification'])
        self.assertIsNone(outcome['clarification_question'])
        self.assertIn('paying guest',str(outcome['known_meanings']))

    def test_production_preserves_clarification_and_stops_before_asset_collection(self):
        from hinglish_visuals.pipeline import resolve_visual_entity,save_resolution_outcomes
        from hinglish_visuals.planner import VisualMoment,VisualClarificationRequired
        moment=VisualMoment(0,'PG',['PG'],2,'PG','PG','pg','PG','photo','popup')
        outcomes={}
        entity=resolve_visual_entity(Brain(**self.reply(id='',referent='ambiguous',compatible=False)),Web(PG_RESULTS),
            {'key':'pg','name':'PG','kind':'place','about':''},{},[moment],
            [SimpleNamespace(id=0,text='PG')],review_options=True,progress=lambda _:None,resolution_outcomes=outcomes)
        self.assertIsNone(entity)
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint=Path(tmp)/'job/visuals-checkpoint.json'
            with patch.dict('os.environ',{'STORYLENS_VISUALS_CHECKPOINT':str(checkpoint)}), \
                 self.assertRaises(VisualClarificationRequired) as error:
                save_resolution_outcomes(Path(tmp),outcomes)
            saved=json.loads((Path(tmp)/'visuals-resolution.json').read_text('utf-8'))
            self.assertTrue(saved['needs_clarification'])
            self.assertIn('PG',str(error.exception))
            self.assertEqual(error.exception.resolution['outcomes'],saved['outcomes'])
            receipt=json.loads((checkpoint.parent/'visuals-clarification.json').read_text('utf-8'))
            self.assertEqual(receipt['resolution_file'],str((Path(tmp)/'visuals-resolution.json').resolve()))
            self.assertEqual(receipt['questions'],saved['questions'])
            self.assertFalse(checkpoint.exists())  # not a resumable-media success marker


if __name__=='__main__':unittest.main()
