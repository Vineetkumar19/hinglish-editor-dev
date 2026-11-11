"""One exact public image URL, original bytes retained, no inference/search."""
import hashlib
import io
import json
from pathlib import Path
import re
import threading
import time
from PIL import Image,ImageOps
from hinglish_photos.network import Fetcher,validate_url

FORMATS={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','AVIF':'.avif','GIF':'.gif','TIFF':'.tif','BMP':'.bmp'}

class ImageDownloads:
    def __init__(self,root,fetcher_factory=Fetcher):
        self.base=Path(root).resolve()/'output/image-downloads'
        self.downloads=self.base/'Downloads';self.records=self.base/'records'
        self.fetcher_factory=fetcher_factory;self.lock=threading.RLock()

    def download(self,url):
        try:
            validate_url(url)
            result=self.fetcher_factory().get(url,limit=25*1024**2,kind='image')
            return self.ingest(result['data'],url,result['url'])
        except Exception as error:
            raise ValueError('Image download: '+str(error)) from error

    def ingest(self,data,url='',source_url='clipboard'):
        try:
            if len(data)>25*1024**2:raise ValueError('Choose an image smaller than 25 MB.')
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in FORMATS or image.width*image.height>60_000_000:raise ValueError('Choose a supported image smaller than 60 megapixels.')
                fmt=image.format;width,height=image.size;image.verify()
            digest=hashlib.sha256(data).hexdigest();key=digest[:24]
            with self.lock:
                self.downloads.mkdir(parents=True,exist_ok=True);self.records.mkdir(parents=True,exist_ok=True)
                original=self.downloads/('Image-'+digest[:16]+FORMATS[fmt])
                if original.exists():
                    if hashlib.sha256(original.read_bytes()).hexdigest()!=digest:raise ValueError('A saved download changed; keep it and download into a fresh location.')
                else:
                    with original.open('xb') as stream:stream.write(data)
                native=original
                if fmt in ('WEBP','AVIF'):
                    # AE-compatible derivative; original downloaded bytes remain intact.
                    native=self.downloads/('Image-'+digest[:16]+'.png')
                    with Image.open(original) as image:
                        image=ImageOps.exif_transpose(image);buffer=io.BytesIO()
                        image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(buffer,'PNG',icc_profile=image.info.get('icc_profile'))
                    compatible=buffer.getvalue()
                    if len(compatible)>100*1024**2:raise ValueError('The editor-compatible image is too large. Use a smaller source image.')
                    if native.exists():
                        if native.read_bytes()!=compatible:raise ValueError('The editor copy changed. Your original is kept; restore its saved copy before adding it.')
                    else:
                        with native.open('xb') as stream:stream.write(compatible)
                row={'id':key,'sha256':digest,'url':url,'source_url':source_url,'format':fmt,'width':width,'height':height,
                     'original':original.name,'native':native.name,'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'saved_at':time.time()}
                record=self.records/(key+'.json')
                if record.exists():row['imports']=json.loads(record.read_text('utf8')).get('imports',[])
                self._save(row)
                return row
        except Exception as error:
            raise ValueError('Image download: '+str(error)) from error

    def _save(self,row):
        path=self.records/(row['id']+'.json');temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');temp.replace(path)

    def load(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{24}',key):raise ValueError('Image download: choose the saved image again.')
        path=self.records/(key+'.json')
        if not path.is_file():raise ValueError('Image download: this saved image is unavailable; paste its link again.')
        return json.loads(path.read_text('utf8'))

    def file(self,key,kind='original'):
        row=self.load(key)
        if kind not in ('original','native'):raise ValueError('Image download: choose the original or editor image.')
        path=(self.downloads/row[kind]).resolve()
        digest=row['sha256'] if kind=='original' else row['native_sha256']
        if not path.is_relative_to(self.downloads.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Image download: the saved image is missing or changed; paste its link again.')
        return path

    def manifest(self,key,project_id):
        row=self.load(key);path=self.file(key,'native')
        if not project_id:raise ValueError('Image import: open the intended After Effects project first.')
        return {'id':key,'path':str(path),'sha256':row['native_sha256'],'expected_project_id':project_id,'folder':'Image Downloader'}

    def accept(self,key,project_id,receipt):
        manifest=self.manifest(key,project_id)
        if not isinstance(receipt,dict) or not receipt.get('ok') or receipt.get('id')!=key or receipt.get('project_id')!=project_id or receipt.get('folder') not in ('Image Downloader','Downloads') or not receipt.get('footage_id') or Path(receipt.get('path','')).resolve()!=Path(manifest['path']).resolve():
            raise ValueError('Image import: After Effects has not confirmed this image in Image Downloader. The saved image is kept; retry adding it.')
        with self.lock:
            row=self.load(key);imports=[r for r in row.get('imports',[]) if r.get('project_id')!=project_id]
            row['imports']=imports+[receipt];self._save(row)
        return row

_services={};_lock=threading.Lock()
def service(root):
    key=str(Path(root).resolve())
    with _lock:
        if key not in _services:_services[key]=ImageDownloads(root)
        return _services[key]
