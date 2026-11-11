"""Isolated controller/source fixtures; no actual model or network acceptance."""
import copy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from hinglish_visuals.web import Entity,Media,Web
from hinglish_visuals.websearch import WebSearch
from hinglish_visuals.planner import resolve_entity,VisualMoment
from hinglish_visuals.references import reference_method
from hinglish_visuals.gather import gather
from tests.test_visuals_generic_retrieval import fixture,picture


class Brain:
    def __init__(self,*replies):self.replies=list(replies);self.calls=[]
    def json(self,system,data,schema,**kwargs):
        self.calls.append((system,copy.deepcopy(data),schema,kwargs))
        return copy.deepcopy(self.replies.pop(0))


def reply(**changes):
    return {'id':'Q188507','referent':'named','compatible':True,'constraints_match':True,
        'reason':'Synthetic recorded-decision controller fixture',**changes}


class Canonical:
    def __init__(self,subclasses=('Q3305339','Q699405')):self.subclasses=list(subclasses);self.fetched=[];self.class_reads=[]
    def search_entities(self,name):return [dict(id='Q188507',label='apartment',description='self-contained housing unit occupying part of a building')]
    def classification(self,qid):
        self.class_reads.append(qid)
        return dict(qid=qid,subclass_of=self.subclasses,instance_of=['Q1247867'],source='https://www.wikidata.org/wiki/'+qid)
    def entity(self,key,name,kind,qid):
        self.fetched.append(qid);return Entity(key,name,kind,qid,label='apartment',description='self-contained housing unit occupying part of a building')


def context():
    return dict(country='India',moments=[dict(quote='abhi flat to mil hi jaega',mention='flat',
        meaning='Finding a flat would be easy',category='room',visual='An apartment in North India')],
        speech=[dict(id=1,text='abhi flat to mil hi jaega')],story=['Finding housing'])


class ClassSourceEvidenceTests(unittest.TestCase):
    def test_canonical_class_requires_local_reconsideration_not_unique_property(self):
        b=Brain(reply(),reply(id='',referent='generic',compatible=False))
        w=Canonical();out={};ctx=context();summary=dict(country='India',creator_guidance={'all':['first','last']})
        before=copy.deepcopy((ctx,summary))
        found=resolve_entity(b,w,dict(key='flat',name='Flat',kind='place',about='accommodation'),summary,
            resolution_context=ctx,resolution_outcome=out)
        self.assertIsNone(found);self.assertEqual(w.fetched,[]);self.assertEqual(len(b.calls),2)
        self.assertEqual((out['status'],out['referent']),('generic','generic'))
        self.assertEqual(out['canonical_class_evidence']['subclass_of'],['Q3305339','Q699405'])
        self.assertEqual(b.calls[1][1]['resolution_context'],ctx)
        self.assertEqual(b.calls[1][1]['video_context'],summary)
        self.assertEqual((ctx,summary),before)

    def test_class_repeated_named_or_failed_constraints_stays_unresolved(self):
        for second in [reply(),reply(id='',referent='generic',compatible=False,constraints_match=False)]:
            b=Brain(reply(),second);w=Canonical();out={}
            found=resolve_entity(b,w,dict(key='flat',name='Flat',kind='place',about='housing'),{},
                resolution_context=context(),resolution_outcome=out)
            self.assertIsNone(found);self.assertEqual(w.fetched,[])
            self.assertEqual(out['status'],'unresolved')

    def test_individual_and_default_resolution_do_not_change(self):
        for ctx in [None,context()]:
            b=Brain(reply());w=Canonical(subclasses=())
            found=resolve_entity(b,w,dict(key='flat',name='Flat',kind='place',about='housing'),{},resolution_context=ctx)
            self.assertEqual(found.qid,'Q188507');self.assertEqual(len(b.calls),1)
            self.assertEqual(len(w.class_reads),0 if ctx is None else 1)
        for kind,category in [('person','person'),('brand','logo'),('place','temple')]:
            w=Canonical();b=Brain(reply());ctx=context();ctx['moments'][0]['category']=category
            with patch('hinglish_visuals.planner.fits_kind',return_value=True),patch('hinglish_visuals.planner.model_rules.sounds_like',return_value=True):
                resolve_entity(b,w,dict(key='x',name='Named Subject',kind=kind,about='specific subject'),{},resolution_context=ctx)
            self.assertEqual(w.class_reads,[])

    def test_wikidata_classification_is_structured_source_data(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Web(temp)
            claims={'P279':[{'mainsnak':{'snaktype':'value','datavalue':{'value':{'id':'Q_PARENT'}}}}],
                    'P31':[{'mainsnak':{'snaktype':'value','datavalue':{'value':{'id':'Q_TYPE'}}}}]}
            item={'claims':claims,'labels':{'en':{'value':'apartment'}},'aliases':{'en':[{'value':'flat'}]}}
            with patch.object(w,'get',return_value={'entities':{'Q123':item}}):r=w.classification('Q123')
            self.assertEqual(r['subclass_of'],['Q_PARENT']);self.assertEqual(r['instance_of'],['Q_TYPE'])
            self.assertEqual(r['qid'],'Q123')
            self.assertEqual(r['label'],'apartment');self.assertEqual(r['aliases'],['flat'])

    def test_confirmed_generic_class_retains_source_aliases_without_named_adoption(self):
        _,entry,project=fixture()
        project['resolution_outcomes']['pg']['canonical_class_evidence']={
            'qid':'Q123','subclass_of':['Q2'],'label':'rental accommodation','aliases':['paying guest room'],
            'source':'https://www.wikidata.org/wiki/Q123'}
        method=reference_method(entry,project)
        self.assertIn('rental accommodation',method['names'])
        self.assertIn('paying guest room',method['names'])
        self.assertFalse(project['entities']['pg']['qid'])
        self.assertIsNone(project['resolution_outcomes']['pg'].get('candidate_id'))

    def test_source_page_must_bind_exact_image_and_supply_its_own_geography(self):
        _,entry,project=fixture();method=reference_method(entry,project)
        media=picture('PG room in Gurgaon','A PG room');original=copy.deepcopy(media)
        with tempfile.TemporaryDirectory() as temp:
            finder=WebSearch(temp);finder.begin_subject()
            body='# Gurgaon PG rooms\nThis PG room is in North India.\n![Room]('+media.url+')'
            with patch('hinglish_visuals.reach.read',return_value=body) as read:
                enriched=finder.source_evidence(media,method)
            self.assertIn('North India',enriched.text);self.assertEqual(media,original);read.assert_called_once()
        for body in ['PG rooms North India ![Room](https://other.test/unrelated.jpg)',
                     '# PG rooms\n![Room]('+media.url+')\nThis room is in Canada.',None]:
            with tempfile.TemporaryDirectory() as temp:
                finder=WebSearch(temp);finder.begin_subject()
                with patch('hinglish_visuals.reach.read',return_value=body):r=finder.source_evidence(media,method)
                from hinglish_visuals.web import generic_source_matches
                self.assertFalse(generic_source_matches(method,r.title+' '+r.text))

    def test_gather_enriches_before_gate_even_when_image_search_has_many_results(self):
        entity,entry,project=fixture();method=reference_method(entry,project)
        media=picture('PG room in Gurgaon','PG room')
        class WebStub:
            def files(self,*a):return []
            def lead_image(self,*a):return None
            def commons_search(self,*a):return []
        class Finder:
            def __init__(self):self.reads=0
            def images(self,*a):return [media]*30
            def source_evidence(self,m,method):
                self.reads+=1;return replace(m,text=m.text+' PG room in North India')
        moment=VisualMoment(phrase_id=0,visual=entry['visual'],queries=entry['queries'],entity='pg',show='photo',category='room')
        finder=Finder()
        result=gather(WebStub(),moment,entity,2,'portrait',(720,1280),finder=finder,reference_method=method)
        self.assertEqual(len(result),1);self.assertEqual(finder.reads,1)
        finder=Finder();gather(WebStub(),moment,entity,2,'portrait',(720,1280),finder=finder)
        self.assertEqual(finder.reads,0)

    def test_source_read_budget_and_failure_keep_unverified_leads_out(self):
        _,entry,project=fixture();method=reference_method(entry,project)
        with tempfile.TemporaryDirectory() as temp:
            finder=WebSearch(temp);finder.begin_subject()
            with patch('hinglish_visuals.reach.read',side_effect=RuntimeError('fixture unavailable')) as read:
                for i in range(12):
                    m=picture('PG room','PG room');m.page_url='https://example.test/'+str(i)
                    self.assertEqual(finder.source_evidence(m,method),m)
                self.assertLessEqual(read.call_count,4)

    def test_shared_source_page_serves_multiple_bound_images_without_extra_read(self):
        _,entry,project=fixture();method=reference_method(entry,project)
        first=picture('PG room','PG room');second=replace(first,id='second',url='https://example.test/second.jpg')
        body='# PG rooms in North India\n![One]('+first.url+')\n![Two]('+second.url+')'
        with tempfile.TemporaryDirectory() as temp:
            finder=WebSearch(temp);finder.begin_subject()
            with patch('hinglish_visuals.reach.read',return_value=body) as read:
                for media in [first,second]:self.assertIn('North India',finder.source_evidence(media,method).text)
            read.assert_called_once()

    def test_new_source_reader_rejects_local_literals_and_absent_method(self):
        _,entry,project=fixture();method=reference_method(entry,project)
        with tempfile.TemporaryDirectory() as temp:
            finder=WebSearch(temp);finder.begin_subject()
            with patch('hinglish_visuals.reach.read',side_effect=AssertionError('must not read')) as read:
                for page in ['file:///local','http://127.0.0.1/','http://[::1]/','http://192.168.1.3/',
                             'http://localhost/','https://user:secret@example.test/']:
                    media=picture();media.page_url=page
                    self.assertEqual(finder.source_evidence(media,method),media)
                self.assertEqual(finder.source_evidence(picture(),None),picture())
            read.assert_not_called()

    def test_default_duplicate_candidate_can_still_supply_better_metadata(self):
        entity=Entity('subject','Named Subject','person',label='Named Subject')
        small=picture('Named Subject','Named Subject');small.width=20;small.height=20
        good=replace(small,width=700,height=500)
        class WebStub:
            def files(self,*a):return []
            def lead_image(self,*a):return None
            def commons_search(self,*a):return []
        class Finder:
            def images(self,*a):return [small,good]
        moment=VisualMoment(phrase_id=0,visual='Named Subject',queries=['Named Subject'],entity='subject',show='photo',category='person')
        self.assertEqual(len(gather(WebStub(),moment,entity,2,'portrait',(720,1280),finder=Finder())),1)


if __name__=='__main__':unittest.main()
