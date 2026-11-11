"""Render Motion Graphics scenes locally: the HTML template runs in Microsoft Edge / Google Chrome (already on the PC,
driven headless by Playwright), every frame is seeked and captured, and the frames become an MP4 (full-screen scene)
or a QuickTime Animation .mov with transparency (overlay card for your timeline)."""
from fractions import Fraction
from io import BytesIO
from hinglish_cut.compute_policy import h264_profile,ffmpeg_h264
from hinglish_cut.model_preferences import preferred_device
from pathlib import Path
import json

import numpy as np
from PIL import Image

SCENE_PAGE = Path(__file__).resolve().parent / 'web' / 'scene.html'
CHANNELS = ('msedge', 'chrome', None)          # None = Playwright's own Chromium, if it was installed


class SceneRenderer:
    def __new__(cls, width, height, engine='hyperframes', device='cpu'):
        if engine != 'hyperframes':
            from .native_engines import NativeSceneRenderer
            return NativeSceneRenderer(width,height,engine,device=device)
        return super().__new__(cls)

    def __init__(self, width, height, engine='hyperframes', device='cpu'):
        from playwright.sync_api import sync_playwright
        self.width, self.height = width, height
        self.device=device
        # templates are designed for 1080 px on the short side: a 720p or 4K timeline gets the same layout, scaled.
        # A square video uses the 16:9 design, centred on the scene's background.
        self.square = width == height
        design = (1920, 1080) if self.square else (width, height)
        self.scale = min(design) / 1080
        view = {'width': round(design[0] / self.scale), 'height': round(design[1] / self.scale)}
        self.design = (round(view['width'] * self.scale), round(view['height'] * self.scale))
        self._pw = sync_playwright().start()
        self.browser, errors = None, []
        launch_args=['--enable-gpu','--enable-gpu-rasterization','--disable-software-rasterizer'] if device=='cuda' else []
        for channel in CHANNELS:
            try:
                self.browser = self._pw.chromium.launch(channel=channel, headless=True,args=launch_args) if channel else \
                    self._pw.chromium.launch(headless=True,args=launch_args)
                self.name = channel or 'chromium'
                break
            except Exception as error:
                errors.append(f'{channel}: {str(error).splitlines()[0][:120]}')
        if self.browser is None:
            self._pw.stop()
            raise RuntimeError('Motion Graphics needs Microsoft Edge or Google Chrome (' + '; '.join(errors) + ')')
        self.page = self.browser.new_page(viewport=view, device_scale_factor=self.scale)
        self._gpu = None
        if device == 'cuda':
            try:
                from hinglish_cut.browser_gpu import require_browser_gpu
                self.gpu_renderer = require_browser_gpu(self.page)
                from hinglish_cut.gpu_frames import CudaFrames
                self._gpu = CudaFrames()
            except BaseException:
                self.browser.close();self._pw.stop()
                raise
        self.page.goto(SCENE_PAGE.as_uri())
        self._creative = False

    def load(self, scene):
        from .creative import TEMPLATES as creative_templates
        creative = scene.get('template') in creative_templates
        if creative != self._creative:
            self.page.goto((SCENE_PAGE.with_name('creative.html') if creative else SCENE_PAGE).as_uri())
            self._creative = creative
        data = {**scene, 'width': self.design[0], 'height': self.design[1]}    # only the orientation is used
        self.page.evaluate('scene => window.mgLoad(scene)', data)
        self.page.evaluate('document.fonts.ready.then(() => true)')
        self.page.evaluate('() => window.mgReady()')          # every picture decoded before a frame is taken

    def check(self, scene):
        """Layout problems after text fitting (text cut off, blocks outside the frame)."""
        self.load(scene)
        return self.page.evaluate('() => window.mgCheck()')

    def frame(self, seconds, alpha=False):
        self.page.evaluate('t => window.mgSeek(t)', seconds)
        if alpha:
            image = Image.open(BytesIO(self.page.screenshot(type='png', omit_background=True))).convert('RGBA')
        else:
            image = Image.open(BytesIO(self.page.screenshot(type='jpeg', quality=93))).convert('RGB')
        if self.square:
            if self._gpu is not None:
                inner=self._gpu.resize(self._gpu.upload(np.asarray(image)),self.width,round(self.width*image.height/image.width),'bicubic')
                if alpha:
                    # Transparent MOV export is rejected before frame production.
                    raise RuntimeError('GPU-only transparent export is unavailable in this path.')
                rgb=self.page.evaluate('() => getComputedStyle(document.getElementById("stage")).backgroundColor.match(/[0-9.]+/g).slice(0, 3).map(Number)')
                canvas=self._gpu.blank(self.width,self.height)
                canvas[:]=self._gpu.torch.tensor(rgb,device='cuda').view(1,3,1,1)
                y=(self.height-inner.shape[-2])//2
                canvas[...,y:y+inner.shape[-2],:]=inner[:,:3]
                return self._gpu.download(canvas)
            inner = image.resize((self.width, round(self.width * image.height / image.width)), Image.LANCZOS)
            background = (0, 0, 0, 0) if alpha else tuple(self.page.evaluate(
                '() => getComputedStyle(document.getElementById("stage")).backgroundColor.match(/[0-9.]+/g).slice(0, 3).map(Number)'))
            canvas = Image.new(image.mode, (self.width, self.height), background)
            canvas.paste(inner, (0, (self.height - inner.height) // 2))
            image = canvas
        elif image.size != (self.width, self.height):        # a scale that is not a whole number can be 1 px off
            if self._gpu is not None:
                return self._gpu.download(self._gpu.resize(self._gpu.upload(np.asarray(image)),self.width,self.height,'bicubic'))
            image = image.resize((self.width, self.height), Image.LANCZOS)
        return np.asarray(image)

    def still(self, scene, seconds, target):
        self.load(scene)
        Image.fromarray(self.frame(seconds, alpha=scene.get('mode') == 'overlay')).save(target)
        return Path(target)

    def render(self, scene, target, fps, progress=None):
        """Write the scene: MP4 for a full-screen scene, transparent .mov for an overlay."""
        from hinglish_shorts.render import _Video
        alpha = scene.get('mode') == 'overlay'
        if alpha and self.device == 'cuda':
            raise RuntimeError('Transparent Motion Graphics MOV export has no GPU encoder in this path. CPU fallback is disabled. Keep the scene and use a GPU MP4 export or native editable handoff.')
        from .creative import TEMPLATES as creative_templates
        if scene.get('template') in creative_templates and not alpha and not self.square:
            from .creative_export import render_hyperframes
            return render_hyperframes(scene, target, fps, self.width, self.height, progress,device=self.device)
        writer = _Video(Path(target), self.width, self.height, Fraction(fps), 'qtrle' if alpha else h264_profile(self.device)[0])
        try:
            self.write_scene(writer, scene, fps, alpha, audit_folder=Path(target).with_suffix('.motion') if scene.get('continuity_audit') else None)
            return writer.finish()
        except BaseException:
            writer.abort()
            raise

    def write_scene(self, writer, scene, fps, alpha=False, frames=None, audit_folder=None):
        """Append the scene's frames to an open writer (the standalone video is many scenes in one file)."""
        self.load(scene)
        count = frames if frames is not None else max(1, round(float(scene['duration']) * float(fps)))
        collector=None;previous=None;photo_traces=[]
        if audit_folder is not None:
            from hinglish_niche.continuous_motion import ContinuousMotionScan
            collector=ContinuousMotionScan(audit_folder)
        try:
            for n in range(count):
                pixels=self.frame(n / float(fps), alpha)
                if collector is not None:
                    if hasattr(self,'page'):
                        from hinglish_niche.photo_continuity import TRACE_JS
                        photo_traces.append(self.page.evaluate(TRACE_JS))
                    reduced=np.asarray(Image.fromarray(pixels[:,:,:3]).resize((256,144),Image.Resampling.BILINEAR))
                    delta=float(np.abs(reduced.astype(np.float32)-previous).mean()) if previous is not None else 0
                    collector(reduced,n/float(fps),n,delta);previous=reduced.astype(np.float32)
                writer.write(pixels, 'rgba' if alpha else 'rgb24')
        finally:
            if collector is not None:
                from hinglish_niche.continuous_motion import continuity_review
                result=continuity_review(collector.close())
                if photo_traces:
                    from hinglish_niche.photo_continuity import review
                    photos=review(photo_traces,fps)
                    result['foreground_photo_geometry']=photos
                    if photos['available']:
                        result['needs_review']=photos['needs_review'];result['warnings']=photos['warnings']
                    (Path(audit_folder)/'photo-geometry.json').write_text(json.dumps(photo_traces,separators=(',',':')),encoding='utf8')
                (Path(audit_folder)/'review.json').write_text(json.dumps(result,indent=2),encoding='utf8')
        return count

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()
            if self._gpu is not None:self._gpu.close()


def scene_json(scene):
    return json.dumps(scene, ensure_ascii=False)
