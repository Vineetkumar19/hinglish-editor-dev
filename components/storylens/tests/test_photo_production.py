import subprocess
import tempfile
from pathlib import Path
import unittest
from tests.test_photo_collector import ROOT
from tests import test_photo_collection_service as fixtures
from hinglish_photos.aftereffects import make_script
from hinglish_photos.service import PhotoService

class PhotoProductionTests(unittest.TestCase):
    def test_search_does_not_announce_done_before_automatic_native_upgrade_receipt(self):
        import threading
        entered=threading.Event();release=threading.Event()
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-native-finish-') as tmp:
            service,data,_=fixtures.CollectionServiceTests().make_service(Path(tmp))
            def importer(folder,job,paths,**kwargs):
                if paths:entered.set();release.wait(5)
                return {'status':'done','project':{'path':'project.aep','root':1},'imported':[],'already_present':[]}
            service.importer=importer;up=service.upload(data);job=service.start({'upload_id':up['upload_id'],'destination':'aftereffects','min_edge':0})
            try:
                self.assertTrue(entered.wait(5));self.assertEqual(service.snapshot(job['id'])['status'],'running','The browser must keep polling until the final native receipt arrives.')
            finally:release.set();service.wait(job['id'],10)
    def test_preview_upgrade_replaces_the_existing_native_item_without_duplicates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-production-upgrade-') as tmp:
            scripts=[]
            for name,origin in (('preview','screenshot-preview'),('original','original')):
                path=Path(tmp)/(name+'.js');source='D:/'+name+'.png'
                path.write_text(make_script({'id':'same','name':'RECEIPT','paths':[source],'photos':[{'id':1,'path':source,'origin':origin}],'expected':None},'D:/'+name+'-receipt.json'),'utf8');scripts.append(str(path))
            result=subprocess.run(['node',str(ROOT/'tests/photo-ae-upgrade-fixture.cjs'),*scripts],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_trash_and_restore_preserve_native_linked_paths_across_service_reopen(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-production-trash-') as tmp:
            service,data,_=fixtures.CollectionServiceTests().make_service(Path(tmp))
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id'],'min_edge':0});service.wait(job['id'],10);service.save(job['id'])
            source=service.file(job['id'],'photo',1);before=source.read_bytes()
            service.update(job['id'],ae_receipt={'status':'done','imported':[{'path':str(source)}]})
            service.archive(job['id'])
            self.assertTrue(source.is_file(),'Trash must not invalidate an Adobe media reference.')
            reopened=PhotoService(Path(tmp));self.assertEqual(reopened.snapshot(job['id'])['status'],'archived')
            reopened.restore(job['id']);self.assertEqual(reopened.file(job['id'],'photo',1),source)
            self.assertEqual(source.read_bytes(),before)

    def test_user_names_never_participate_in_script_template_replacement(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-production-name-') as tmp:
            script=Path(tmp)/'name.js'
            for name in ('RECEIPT','MANIFEST RECEIPT','quotes " and \\ paths','Images → Screenshot 15'):
                script.write_text(make_script({'id':'test','name':name,'paths':[],'expected':None},'D:/RECEIPT/receipt.json'),'utf8')
                result=subprocess.run(['node','--check',str(script)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,(name,result.stderr))

    def test_default_recovers_originals_at_least_as_large_as_each_screenshot_photo(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-production-size-') as tmp:
            service,data,_=fixtures.CollectionServiceTests().make_service(Path(tmp))
            upload=service.upload(data);job=service.start({'upload_id':upload['upload_id']});service.wait(job['id'],10)
            result=service.snapshot(job['id']);self.assertEqual(result['photos'][0]['status'],'ready',result)

    def test_reference_minimum_checks_both_photo_axes_and_real_matching_detail(self):
        from hinglish_photos.quality import meets_quality
        row={'box':[0,0,300,200],'width':600,'height':400,'effective_width':600,'effective_height':400}
        self.assertTrue(meets_quality(row,0))
        self.assertFalse(meets_quality({**row,'effective_height':150},0))
        self.assertFalse(meets_quality({**row,'width':250,'effective_width':250},0))
        self.assertFalse(meets_quality(row,1280))

if __name__=='__main__':unittest.main()
