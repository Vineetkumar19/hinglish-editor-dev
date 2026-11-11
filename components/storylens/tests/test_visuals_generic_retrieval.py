"""CPU fixtures for typed generic references; no real source/model acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from hinglish_visuals.web import Entity, Media
from hinglish_visuals.gather import gather, locked
from hinglish_visuals.references import context_info, reference_method, candidate_info, collect
from hinglish_visuals.evaluator import decide, Evaluator
from hinglish_visuals.planner import VisualMoment


def fixture():
    entity = Entity('pg', 'PG', 'place', label='PG')
    entry = dict(entity='pg', label='PG', text='PG mein', quote='PG mein', meaning='PG (paying guest) accommodation',
        visual='A PG room in North India', queries=['PG room North India'], show='photo', category='room',
        reference_type='identity', evidence_terms=[])
    resolution = dict(entity_key='pg', original_name='PG', status='generic', referent='generic',
        known_meanings=['PG (paying guest) accommodation'], quoted_words=['PG mein'],
        country='India', needs_clarification=False)
    project = dict(entities={'pg':entity.to_dict()}, resolution_outcomes={'pg':resolution}, summary={}, slots=[entry])
    return entity, entry, project


def picture(title='PG room in North India', text='A paying guest room in North India'):
    return Media('image', 'web', title, title, 'https://example.test/room.jpg',
        page_url='https://example.test/rooms', width=900, height=600, text=text)


def answer(**changes):
    return dict(category_ok=True, category_seen='room', fits_moment=True, quality_ok=True,
        identity='unsure', class_visible=True, seen='A clear bedroom', **changes)


class GenericReferenceTests(unittest.TestCase):
    def test_typed_generic_only_not_boolflip_or_automatic_acronym(self):
        entity, entry, project = fixture()
        method = reference_method(entry, project)
        self.assertEqual(method['mode'], 'generic_class')
        self.assertIn('paying guest', method['names'])
        self.assertEqual(entity.names(), [])
        self.assertEqual(entity.names(min_length=2), ['PG'])
        for field,value in [('status','resolved'),('referent','named'),('needs_clarification','false'),('original_name','Different')]:
            p=copy.deepcopy(project); p['resolution_outcomes']['pg'][field]=value
            self.assertEqual(reference_method(entry,p), {}, field)
        for kind in ['person','brand','event']:
            p=copy.deepcopy(project);p['entities']['pg']['kind']=kind
            self.assertEqual(reference_method(entry,p), {})
        for change in [{'reference_type':'evidence'},{'evidence_terms':['runs']},{'show':'logo'}]:
            self.assertEqual(reference_method({**entry,**change},project), {})
        p=copy.deepcopy(project);p['entities']['pg']['qid']='Q123'
        self.assertEqual(reference_method(entry,p), {})

    def test_optional_resolution_metadata_is_fail_closed(self):
        _,entry,project=fixture()
        for value in [None,[],True,'generic']:
            p=copy.deepcopy(project);p['resolution_outcomes']=value
            self.assertEqual(reference_method(entry,p),{})
        for field,value in [('known_meanings',None),('quoted_words',[]),('country',None),
                            ('candidate_id','Q123'),('canonical_name','Some named building')]:
            p=copy.deepcopy(project);p['resolution_outcomes']['pg'][field]=value
            self.assertEqual(reference_method(entry,p),{},field)

    def test_short_name_needs_class_context_and_source_country(self):
        entity,entry,project=fixture();method=reference_method(entry,project)
        self.assertTrue(locked(picture(),entity,reference_method=method))
        for media in [picture('PG logo in North India','Procter Gamble logo'),
                      picture('PG room in Canada','A PG room Canada'),
                      picture('PG room in South India','A PG room South India'),
                      picture('Project Gutenberg in North India','An ebook library'),
                      picture('PG rooms','PG rooms')]:
            self.assertFalse(locked(media,entity,reference_method=method),media.title)
        self.assertFalse(locked(picture(),entity))
        self.assertFalse(locked(picture(),entity,reference_method={'mode':'generic_class'}))

    def test_actual_gather_path_uses_optional_context_default_unchanged(self):
        entity,entry,project=fixture();method=reference_method(entry,project)
        class Web:
            def files(self,*a): return []
            def lead_image(self,*a): return None
            def commons_search(self,*a): return []
        class Finder:
            def images(self,*a): return [picture(),picture('PG logo','Logo'),picture('PG room Canada','PG room Canada')]
        moment=VisualMoment(phrase_id=0,visual=entry['visual'],queries=entry['queries'],entity='pg',
            show='photo',category='room',reference_type='identity')
        args=(Web(),moment,entity,2,'vertical',(720,1280))
        self.assertEqual(len(gather(*args,finder=Finder(),reference_method=method)),1)
        self.assertEqual(gather(*args,finder=Finder()),[])

    def test_generic_class_is_not_unique_building_identity(self):
        _,entry,project=fixture(); info=context_info(entry,project)
        info['source_evidence']='PG room in North India'
        self.assertTrue(decide(answer(),info).passed)
        self.assertEqual(info['reference_method']['mode'],'generic_class')
        for key,val in [('class_visible',False),('class_visible','true'),('category_ok',False),
                        ('fits_moment',False),('quality_ok',False)]:
            a=answer();a[key]=val
            self.assertFalse(decide(a,info).passed,key)
        a=answer();a.pop('class_visible');self.assertFalse(decide(a,info).passed)
        self.assertFalse(decide(answer(),{**info,'source_evidence':'PG room Canada'}).passed)
        self.assertFalse(decide(answer(),{**info,'source_evidence':''}).passed)

    def test_named_and_default_shared_callers_remain_strict(self):
        for kind,name in [('person','Virat Kohli'),('place','Taj Mahal'),('event','IPL final'),('thing','cup')]:
            info=dict(name=name,kind=kind,show='photo',category='room',visual=name,strict_context=True)
            self.assertFalse(decide(answer(),info).passed)
            self.assertFalse(decide(answer(),{**info,'reference_method':{'mode':'generic_class'}}).passed)
        # Existing non-strict/default B-roll/Sound semantics are unchanged.
        default=dict(name='room',kind='thing',show='photo',category='room',visual='room')
        old=decide(answer(),default)
        self.assertTrue(old.passed);self.assertEqual(len(old.warnings),1)

    def test_optional_generic_schema_and_default_model_contract(self):
        _,entry,project=fixture();info=context_info(entry,project);info['source_evidence']='PG room North India'
        class Model:
            name='synthetic CPU fixture'
            def __init__(self): self.calls=[]
            def look(self,images,system,schema=None):
                self.calls.append((system,schema));return answer()
        model=Model();evaluator=Evaluator(model,None,lambda _:None)
        self.assertTrue(evaluator._check([Image.new('RGB',(400,400))],info,'a picture','photo').passed)
        system,schema=model.calls[-1]
        self.assertIn('class_visible',schema['required'])
        self.assertIn('not the speaker',system)
        default=dict(name='Taj Mahal',kind='place',show='photo',category='building',visual='Taj Mahal',strict_context=True)
        evaluator._check([Image.new('RGB',(400,400))],default,'a picture','photo')
        self.assertIsNone(model.calls[-1][1])

    def test_collect_passes_source_evidence_and_saves_illustration_not_selection(self):
        entity,entry,project=fixture()
        entry.update(index=0,start=0.,end=2.,priority=3,display='popup',rejected=[],options=[],
                     alternatives=[],chosen=None,clip=None,evaluation=None)
        class Web:
            session=None
            def files(self,*a): return []
            def lead_image(self,*a): return None
            def commons_search(self,*a): return []
        class Finder:
            def images(self,*a): return [media]
        class Model:
            name='synthetic CPU fixture'
            def look(self,images,system,schema=None): return answer()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'review';folder.mkdir()
            path=root/'fixture.png';Image.new('RGB',(400,500),(30,50,90)).save(path)
            media=picture();media.path=str(path)
            with patch('hinglish_visuals.references.judge',side_effect=lambda b,m,e,c,**kw:c), \
                 patch('hinglish_visuals.pipeline.write_outputs'),patch('hinglish_visuals.report.write_report'):
                collect(root,[(SimpleNamespace(orientation='portrait',width=720,height=1280),folder,project)],
                    None,Web(),Finder(),SimpleNamespace(vision_check_model='local'),lambda _:None,
                    Evaluator(Model(),None,lambda _:None))
            self.assertEqual(len(entry['options']),1)
            option=entry['options'][0]
            self.assertEqual(option['reference_method']['scope'],'illustration')
            self.assertTrue(option['evaluation']['checks']['class_visible'])
            self.assertIsNone(entry['chosen']);self.assertIsNone(entry['clip'])
            from hinglish_visuals.recovery import context_key
            info=context_info(entry,project)
            self.assertEqual(option['check_context'],context_key(candidate_info(info,option)))
            changed={**option,'text':'PG room in Canada'}
            changed['title']='PG room in Canada'
            self.assertNotEqual(option['check_context'],context_key(candidate_info(info,changed)))
            self.assertEqual(project['research_state']['stage'],'partial')

    def test_broll_sound_shared_import_contracts_are_unchanged(self):
        from hinglish_broll.verify import Checker
        from hinglish_visuals.evaluator import CHECK_SCHEMA, GENERIC_CHECK_SCHEMA, _png64, _for_model
        with tempfile.TemporaryDirectory() as temp, patch('hinglish_visuals.evaluator.VisionModel') as model:
            model.return_value.name='synthetic CPU contract fixture'
            model.return_value.look.return_value={'seen':'fixture'}
            checker=Checker(Path(temp))
            images=[Image.new('RGB',(3,4))]
            checker._look(images,'B-roll caller system')
            model.return_value.look.assert_called_once()
            args=model.return_value.look.call_args.args
            self.assertEqual(args[:2],(images,'B-roll caller system'))
            self.assertIn(args[2:],((),(None,)))
        self.assertNotIn('class_visible',CHECK_SCHEMA['properties'])
        self.assertIn('identity',CHECK_SCHEMA['required'])
        self.assertIn('class_visible',GENERIC_CHECK_SCHEMA['required'])
        # Sound imports these actual picture helpers, not the optional generic evaluator.
        image=_for_model(Image.new('RGB',(1000,500)))
        self.assertEqual(image.size,(768,384));self.assertTrue(_png64(image).startswith('iVBOR'))


if __name__=='__main__': unittest.main()
