import builtins,hashlib,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from hinglish_app.adobe_framing import analyze,VERSION

class CopyPasteMemoryTests(TestCase):
 def test_cached_face_bounds_do_not_import_or_load_image_libraries(self):
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as temp:
   root=Path(temp);image=root/'photo.jpg';image.write_bytes(b'cache identity fixture');stat=image.stat()
   key=hashlib.sha256(json.dumps([VERSION,str(image.resolve()),stat.st_size,stat.st_mtime_ns]).encode()).hexdigest()
   folder=root/'cache/editor-panel/subject-framing';folder.mkdir(parents=True);saved={'version':1,'faces':[],'width':1920,'height':1080};(folder/(key+'.json')).write_text(json.dumps(saved))
   normal=builtins.__import__
   def limited(name,*args,**kwargs):
    if name.split('.')[0] in ('cv2','numpy','PIL'):raise AssertionError('A cache hit must not load the image runtime')
    return normal(name,*args,**kwargs)
   with patch('builtins.__import__',side_effect=limited):self.assertEqual(analyze(image,root),saved)
