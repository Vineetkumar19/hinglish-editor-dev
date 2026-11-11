"""Preserve the owner's real portrait pixels; remove only the flattened background locally."""
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image


def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'library/thumbnail-styles/kkr-underrated'
    target.mkdir(parents=True,exist_ok=True)
    source=Path('D:/Editing/documentry edit/final videos/final thumbnails/kkr/1.png')
    shutil.copyfile(source,target/'reference.png')
    with Image.open(source) as im:
        upper=im.convert('RGB').crop((0,0,1920,728))
    upper.save(target/'portrait-source.png')
    print('Waiting for the shared GPU queue for local background removal',flush=True)
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_motion.assets import Remover
    with gpu_lock(root):
        print('Removing the background locally; original faces and clothing are preserved',flush=True)
        remover=Remover(root)
        people=remover(upper,'person')
        people.save(target/'people.png')
        receipt={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                 'crop':[0,0,1920,728],'method':'Local BiRefNet foreground removal from owner-supplied reference; no face synthesis',
                 'cutout_receipt':getattr(remover,'last_receipt',{}),'providers':remover.last_providers}
        (target/'cutout-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Real portrait cutout saved: '+str(target/'people.png'),flush=True)


if __name__=='__main__':main()
