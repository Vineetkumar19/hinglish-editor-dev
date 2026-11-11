"""Create an original local texture plate; never use the supplied KKR image pixels."""
import json
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'library/thumbnail-styles/mi-independent-underrated'
    folder.mkdir(parents=True,exist_ok=True)
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_aigen.engine import generate
    item={'id':'mi-atmosphere','kind':'image','width':1280,'height':720,'seed':249119,
          'prompt':'Abstract photographic texture. Electric royal-blue smoke wisps billowing across an empty dark navy void. Golden-orange flames lick upward from both lower corners. Fine bright amber embers and floating ash drift through volumetric cyan fog. Turbulent swirling vapor, dramatic luminous fluid shapes, rich blacks, detailed real smoke, high dynamic range, cinematic light, panoramic horizontal composition. Entire image contains only smoke, flame, sparks and darkness.',
          'out':str(folder/'background.png'),'label':'Original MI blue smoke and golden ember background'}
    print('Waiting for the shared GPU queue for the new local MI background',flush=True)
    with gpu_lock(root):
        results=generate(root,[item],folder/'background-jobs.json',lambda s:print(s,flush=True))
    if not (folder/'background.png').is_file():raise RuntimeError('The local background did not finish. The original photos are saved.')
    (folder/'background-receipt.json').write_text(json.dumps({'engine':'Local Z-Image Turbo','source':'New text-to-image background only; no KKR image input','prompt':item['prompt'],'results':results},indent=2),encoding='utf-8')


if __name__=='__main__':main()
