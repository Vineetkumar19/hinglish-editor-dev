import tempfile,unittest,subprocess
from pathlib import Path
from tests.test_photo_collector import ROOT
from tests import test_photo_collection_service as fixtures

class PhotoPluginTests(unittest.TestCase):
 def test_repeat_import_does_not_overwrite_a_converted_photo_locked_by_adobe(self):
  from hinglish_photos.aftereffects import prepare_files
  from PIL import Image
  from unittest.mock import patch
  with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-native-lock-') as tmp:
   folder=Path(tmp);(folder/'photos').mkdir();source=folder/'photos/source.webp';Image.new('RGB',(640,360),(80,140,200)).save(source,lossless=True)
   rows=[{'id':1,'path':str(source),'origin':'original'}];first,_=prepare_files(folder,[str(source)],rows)
   with patch.object(Image.Image,'save',side_effect=PermissionError('Adobe holds the linked media file open')):
    again,_=prepare_files(folder,[str(source)],rows)
   self.assertEqual(first,again)
 def test_adobe_panel_converts_webp_without_changing_dimensions_or_pixels(self):
  from hinglish_photos.aftereffects import prepare_files
  from PIL import Image
  with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-native-codec-') as tmp:
   folder=Path(tmp);(folder/'photos').mkdir();source=folder/'photos/source.webp'
   image=Image.new('RGB',(640,360),(80,140,200));image.save(source,lossless=True)
   paths,rows=prepare_files(folder,[str(source)],[{'id':1,'path':str(source),'origin':'original'}])
   self.assertEqual(Path(paths[0]).suffix,'.png');self.assertEqual(rows[0]['origin'],'original')
   with Image.open(paths[0]) as converted:self.assertEqual(converted.size,image.size);self.assertEqual(converted.convert('RGB').tobytes(),image.tobytes())
 def test_premiere_native_adapter_normalizes_windows_paths_and_upgrades_same_item(self):
  result=subprocess.run(['node',str(ROOT/'tests/photo-premiere-host-fixture.cjs'),str(ROOT/'hinglish_photos/native_host.jsx')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_standalone_and_packaged_hosts_use_the_same_adapter(self):
  self.assertEqual((ROOT/'hinglish_photos/native_host.jsx').read_bytes(),(ROOT/'editor_plugins/shared/photo-import.jsx').read_bytes())
 def test_typed_manifest_and_receipt_cover_every_photo_and_bind_project(self):
  from hinglish_photos.editor_plugin import prepare,accept_receipt
  with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='photo-plugin-') as tmp:
   service,data,_=fixtures.CollectionServiceTests().make_service(Path(tmp));up=service.upload(data)
   job=service.start({'upload_id':up['upload_id'],'min_edge':0});service.wait(job['id'],10)
   manifest=prepare(service,job['id'],'aftereffects',{'project_id':'owner.aep'})
   self.assertEqual(manifest['type'],'photos');self.assertTrue(manifest['photos'])
   bad={'status':'done','collection_id':job['id'],'host':'aftereffects','project':{'path':'owner.aep','root':0},'folder':{'id':8,'name':'Screenshot 1','parent':'Images'},'imported':[]}
   with self.assertRaises(ValueError):accept_receipt(service,job['id'],'aftereffects',bad)
   rows=[{**r,'photo_id':r['id'],'id':i+10} for i,r in enumerate(manifest['photos'])]
   result=accept_receipt(service,job['id'],'aftereffects',{**bad,'imported':rows})
   self.assertEqual(result['ae_status'],'done')
   self.assertEqual(prepare(service,job['id'],'aftereffects',{'project_id':'owner.aep'})['folder_id'],8)
   with self.assertRaises(ValueError):prepare(service,job['id'],'aftereffects',{'project_id':'different.aep'})

if __name__=='__main__':unittest.main()
