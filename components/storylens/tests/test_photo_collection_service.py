import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image
from tests.test_photo_collector import picture,png,ROOT
from hinglish_photos.service import PhotoService

class CollectionServiceTests(unittest.TestCase):
    def test_heading_worker_can_recover_originals_but_title_alone_cannot_verify_them(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-heading-search-') as tmp:
            service,data,_=self.make_service(Path(tmp))
            class Finder:
                def images(self,query,limit=24):
                    if not query.startswith('"'):return []
                    return [{'url':'https://photos.example/original.png','title':'MI trophy photo'}]
            service.finder=Finder()
            job=service.start({'upload_id':service.upload(data)['upload_id'],'min_edge':0})
            service.wait(job['id'],10)
            result=service.snapshot(job['id'])
            self.assertEqual(result['status'],'done',result)
            self.assertEqual(result['counts']['found'],2)
            self.assertEqual(result['photos'][0]['search_agent'],'heading')
            self.assertNotIn(result['photos'][2]['status'],('ready','saved','duplicate'))
            self.assertEqual({r['agent'] for r in result['photos'][0]['search_agents']},{'visual','heading'})

    def test_originals_without_a_separate_thumbnail_use_the_original_byte_budget(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-large-source-') as tmp:
            service,data,_=self.make_service(Path(tmp))
            class Finder:
                def images(self,*a,**k):return [{'url':'https://photos.example/full.png','title':'full original'}]
            class Fetcher:
                def get(self,url,**kwargs):
                    if kwargs.get('limit',25*1024*1024)<25*1024*1024:raise ValueError('Original was limited to thumbnail bytes')
                    return {'data':png(picture(3)),'url':url,'mime':'image/png'}
            service.finder=Finder();service.fetcher_factory=lambda _:Fetcher()
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10)
            self.assertEqual(service.snapshot(job['id'])['photos'][0]['status'],'ready')
    def test_requested_quality_is_enforced_on_saved_collections_before_download_or_import(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-quality-upgrade-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10)
            with self.assertRaises(ValueError):service.save(job['id'],1,min_edge=1920)
            self.assertEqual(service.snapshot(job['id'])['min_edge'],1920)
            self.assertEqual(service.snapshot(job['id'])['photos'][0]['status'],'low_quality')
            self.assertEqual(list((Path(service.snapshot(job['id'])['output_folder'])/'photos').iterdir()),[])
            service.update(job['id'],ae_status='done',ae_receipt={'status':'done','imported':[]})
            with self.assertRaises(ValueError):service.send_ae(job['id'],min_edge=1920)
            self.assertEqual(service.snapshot(job['id'])['ae_status'],'failed')
    def test_cropped_search_thumbnail_does_not_hide_an_exact_full_size_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-thumb-crop-') as tmp:
            service,data,_=self.make_service(Path(tmp))
            class Fetcher:
                def get(self,url,**kwargs):return {'data':png(picture(3).crop((0,0,640,240)) if 'thumb' in url else picture(3)),'url':url,'mime':'image/png'}
            service.fetcher_factory=lambda _:Fetcher()
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10)
            self.assertEqual(service.snapshot(job['id'])['photos'][0]['status'],'ready')
    def test_later_photos_get_their_own_search_budget(self):
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-later-') as tmp:
            service,data,_=self.make_service(Path(tmp))
            service.analyser=lambda *a,**k:{'title':'MI','query':'global','photos':[{'id':i,'box':[0,0,280,184],'context_box':[0,0,280,240],'caption':'result '+str(i),'publisher':'','query':'photo '+str(i),'description':''} for i in range(1,9)]}
            bad=png(picture(17).resize((96,64)));good=png(picture(3))
            class Finder:
                def images(self,query,limit=30):
                    if query=='photo 8':return [{'url':'https://photos.example/good.png','thumbnail':'https://photos.example/good.png','title':'exact source'}]
                    key=hashlib.sha256(query.encode()).hexdigest()[:8]
                    return [{'url':f'https://photos.example/{key}-{i}.png','title':'unrelated'} for i in range(24)]
            class Fetcher:
                def get(self,url,**kwargs):return {'data':good if 'good.png' in url else bad,'url':url,'mime':'image/png'}
            service.finder=Finder();service.fetcher_factory=lambda _:Fetcher()
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],30)
            self.assertEqual(service.snapshot(job['id'])['photos'][-1]['status'],'ready')
    def test_largest_clean_original_wins_even_when_a_smaller_match_is_found_first(self):
        from PIL import ImageFilter
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-largest-') as tmp:
            service,data,_=self.make_service(Path(tmp))
            source=picture(3).filter(ImageFilter.GaussianBlur(1))
            with Image.open(io.BytesIO(data)) as opened:screenshot=opened.convert('RGB')
            for x in (0,300):screenshot.paste(source.resize((280,184)),(x,0))
            data=png(screenshot)
            class Finder:
                def images(self,*args,**kwargs):return [{'url':'https://photos.example/'+name+'.png','thumbnail':'https://photos.example/thumb.png','title':name} for name in ('small','large')]
            class Fetcher:
                def get(self,url,**kwargs):
                    image=source.resize((1280,840)) if 'large' in url else source
                    return {'data':png(image),'url':url,'mime':'image/png'}
            service.finder=Finder();service.fetcher_factory=lambda _:Fetcher()
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10)
            result=service.snapshot(job['id']);self.assertEqual(result['photos'][0]['width'],1280,result)
    def make_service(self,root):
        first=picture(3);other=picture(17)
        screenshot=Image.new('RGB',(900,300),'#202124')
        for x,photo in ((0,first),(300,first),(600,other)):
            screenshot.paste(photo.resize((280,184)),(x,0))
        plan={'title':'MI 2020','query':'Mumbai Indians 2020','photos':[
            {'id':i+1,'box':[i*300,0,280,184],'context_box':[i*300,0,280,240],
             'caption':'MI trophy photo','publisher':'A publisher','query':'MI trophy',
             'description':'A result photo'} for i in range(3)]}
        calls=[]
        class Finder:
            def images(self,query,limit=30):
                return [{'url':'https://photos.example/original.png','thumbnail':'https://photos.example/thumb.png',
                    'page':'https://publisher.example/story','title':'MI trophy','license':'Usage rights unverified'}]
        class FakeFetcher:
            total=0
            def get(self,url,**kwargs):
                calls.append(url)
                return {'data':png(first if 'original' in url else first.resize((320,210))),
                        'url':url,'mime':'image/png'}
        service=PhotoService(root,analyser=lambda *a,**k:plan,finder=Finder(),fetcher_factory=lambda cancel:FakeFetcher())
        return service,png(screenshot),calls

    def test_collection_saves_original_once_and_never_exports_unmatched_screenshot_crops(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-service-') as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(ROOT))
            service,data,calls=self.make_service(Path(tmp))
            uploaded=service.upload(data)
            job=service.start({'upload_id':uploaded['upload_id'],'min_edge':0})
            service.wait(job['id'],10);result=service.snapshot(job['id'])
            self.assertEqual(result['status'],'done',result)
            self.assertEqual(result['counts']['found'],2)
            self.assertEqual(result['counts']['saved'],0)
            self.assertEqual(list((Path(result['output_folder'])/'photos').iterdir()),[])
            service.save(job['id'])
            result=service.snapshot(job['id'])
            self.assertEqual(result['counts']['saved'],1)
            photo=service.file(job['id'],'photo',1)
            with Image.open(photo) as image:self.assertEqual(image.size,(640,420))
            bundle=service.file(job['id'],'zip')
            with zipfile.ZipFile(bundle) as archive:
                names=archive.namelist()
                self.assertEqual(len([n for n in names if n.startswith('photos/')]),1)
                self.assertIn('sources.csv',names)
                self.assertFalse(any('screenshot' in n or 'creator' in n for n in names))
            self.assertTrue(all(row.get('source_page') for row in result['photos'] if row['status']=='saved'))

    def test_saved_collection_reopens_and_cleanup_is_scoped_and_recoverable(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-store-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10);service.save(job['id'])
            original=service.file(job['id'],'photo',1).read_bytes()
            reopened=PhotoService(Path(tmp))
            self.assertEqual(reopened.snapshot(job['id'])['counts']['saved'],1)
            reopened.archive(job['id'])
            self.assertEqual(reopened.snapshot(job['id'])['status'],'archived')
            with self.assertRaises(ValueError):reopened.file(job['id'],'photo',1)
            reopened.restore(job['id'])
            self.assertEqual(reopened.file(job['id'],'photo',1).read_bytes(),original)
            for bad in ('../outside','', 'a'*31):
                with self.assertRaises(ValueError):reopened.snapshot(bad)
            with self.assertRaises(ValueError):reopened.file(job['id'],'../../outside',1)

    def test_invalid_screenshot_never_creates_a_job(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-bad-') as tmp:
            service=PhotoService(Path(tmp))
            with self.assertRaises(ValueError):service.upload(b'not a screenshot')
            self.assertEqual(service.history(),[])
            with self.assertRaises(ValueError):service.start({'upload_id':'../../secret'})

    def test_retry_keeps_completed_photos_and_same_collection(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-retry-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10);service.save(job['id'])
            first=service.file(job['id'],'photo',1).read_bytes()
            retried=service.retry(job['id']);service.wait(job['id'],10)
            self.assertEqual(retried['id'],job['id'])
            self.assertEqual(service.file(job['id'],'photo',1).read_bytes(),first)
            self.assertEqual(service.snapshot(job['id'])['counts']['saved'],1)

    def test_high_quality_setting_never_saves_a_small_or_upscaled_substitute(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-quality-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':1920});service.wait(job['id'],10)
            result=service.snapshot(job['id'])
            self.assertEqual(result['photos'][0]['status'],'low_quality',result)
            self.assertNotIn('Choose Download',result['stage'])
            with self.assertRaises(ValueError):service.save(job['id'],1)
            self.assertEqual(list((Path(result['output_folder'])/'photos').iterdir()),[])

    def test_single_download_saves_only_the_chosen_original_into_one_collection_folder(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-single-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10)
            result=service.save(job['id'],1)
            files=list((Path(result['output_folder'])/'photos').iterdir())
            self.assertEqual(len(files),1);self.assertEqual(result['photos'][0]['status'],'saved')
            self.assertEqual(result['photos'][1]['status'],'duplicate')
            service.save(job['id'],1)
            self.assertEqual(len(list(files[0].parent.iterdir())),1)

    def test_ae_destination_automatically_saves_verified_photos_and_requires_host_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-auto-') as tmp:
            service,data,_=self.make_service(Path(tmp));calls=[]
            def importer(folder,job,paths,**kwargs):
                calls.append(paths)
                return {'status':'done','project':{'path':'project.aep','root':1},'imported':[{'path':str(p)} for p in paths], 'already_present':[],'receipt':'actual-host-fixture'}
            service.importer=importer
            upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0,'destination':'aftereffects'});service.wait(job['id'],10)
            result=service.snapshot(job['id'])
            self.assertEqual(result['ae_status'],'done',result)
            self.assertEqual(result['counts']['saved'],1)
            self.assertEqual(len(calls),2);self.assertEqual(calls[0],[]);self.assertEqual(len(calls[1]),1)
            with self.assertRaises(ValueError):service.start({'upload_id':upload['upload_id'],'destination':'premiere'})

    def test_legacy_or_changed_banner_variants_are_rechecked_before_native_import(self):
        from PIL import ImageDraw
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-review-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10);service.save(job['id'])
            photo=service.file(job['id'],'photo',1)
            with Image.open(photo) as image:changed=image.convert('RGB')
            ImageDraw.Draw(changed).rectangle((0,310,640,420),fill='red');changed.save(photo)
            calls=[];service.importer=lambda *a,**k:calls.append(a)
            with self.assertRaises(ValueError):service.send_ae(job['id'])
            self.assertEqual(calls,[])
            self.assertEqual(service.snapshot(job['id'])['photos'][0]['status'],'review')

    def test_new_quality_checks_keep_files_already_referenced_by_ae(self):
        from PIL import ImageDraw
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-native-source-') as tmp:
            service,data,_=self.make_service(Path(tmp));upload=service.upload(data)
            job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10);service.save(job['id'])
            photo=service.file(job['id'],'photo',1)
            service.update(job['id'],ae_receipt={'status':'done','imported':[{'path':str(photo)}]})
            with Image.open(photo) as image:changed=image.convert('RGB')
            ImageDraw.Draw(changed).rectangle((0,310,640,420),fill='red');changed.save(photo)
            with self.assertRaises(ValueError):service.send_ae(job['id'])
            self.assertTrue(photo.is_file(),'New quality checks must not break an existing AE footage reference.')

if __name__=='__main__':unittest.main()
