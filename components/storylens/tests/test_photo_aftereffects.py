import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import Mock
from tests.test_photo_collector import ROOT
from hinglish_photos.aftereffects import import_photos,make_script

class AfterEffectsPhotoTests(unittest.TestCase):
    def test_native_host_logic_numbers_screenshots_inside_owner_images_folder(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-host-') as tmp:
            folder=Path(tmp);scripts=[]
            for id in ('first','second'):
                file=folder/(id+'.js');file.write_text(make_script({'id':id,'name':'MI','paths':['D:/a.jpg'],'expected':None},'D:/'+id+'-receipt.json'),'utf8');scripts.append(str(file))
            result=subprocess.run(['node',str(ROOT/'tests/photo-ae-host-fixture.cjs'),*scripts],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_windows_console_launcher_is_used_when_shipped_beside_afterfx(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-console-') as tmp:
            folder=Path(tmp);exe=folder/'AfterFX.exe';console=folder/'AfterFX.com';exe.touch();console.touch();calls=[]
            def runner(args,**kwargs):
                calls.append(args)
                script=Path(args[-1]);receipt=script.with_name(script.stem+'-receipt.json')
                receipt.write_text(json.dumps({'status':'done','imported':[],'already_present':[],'project':{'path':'test.aep','root':1}}),'utf8')
            import_photos(folder,{'id':'abc','title':'MI'},[],find_app=lambda:str(exe),runner=runner,timeout=.1)
            self.assertEqual(calls[0][0],str(console))
    def test_host_script_imports_footage_in_a_named_bin_without_touching_compositions(self):
        script=make_script({'id':'abc','name':'MI "; alert(1); //','paths':['D:/photos/a.jpg'],'expected':None},'D:/receipt.json')
        self.assertIn('new ImportOptions',script);self.assertIn('items.addFolder',script)
        self.assertIn('beginUndoGroup',script);self.assertIn('endUndoGroup',script)
        self.assertNotIn('.layers.add',script);self.assertNotIn('project.save(',script);self.assertNotIn('eval(',script)
        self.assertIn('file.fsName',script);self.assertIn('already_present',script)
    def test_missing_ae_never_launches_an_application_or_claims_an_import(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-') as tmp:
            runner=Mock()
            with self.assertRaisesRegex(ValueError,'Open After Effects'):
                import_photos(Path(tmp),{'id':'abc','title':'MI'},[],find_app=lambda:None,runner=runner)
            runner.assert_not_called()
    def test_success_requires_actual_host_receipt_not_a_successful_launcher_exit(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-ae-') as tmp:
            folder=Path(tmp)
            with self.assertRaisesRegex(ValueError,'confirm'):
                import_photos(folder,{'id':'abc','title':'MI'},[],find_app=lambda:'AfterFX.exe',runner=lambda *a,**k:None,timeout=.01)

if __name__=='__main__':unittest.main()
