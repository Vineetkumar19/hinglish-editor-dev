"""Fail closed when a GPU-required browser selects a software renderer."""
GPU_ASSERT_JS = r'''() => {
 const canvas=document.createElement('canvas');
 const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');
 if(!gl)throw new Error('Hardware browser GPU unavailable; software rendering is disabled.');
 const info=gl.getExtension('WEBGL_debug_renderer_info');
 const name=info?String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)):'';
 if(!name||/swiftshader|llvmpipe|softpipe|software|basic render/i.test(name))
   throw new Error('Hardware browser GPU could not be confirmed; software rendering is disabled.');
 const lose=gl.getExtension('WEBGL_lose_context');if(lose)lose.loseContext();
 return name;
}'''


def require_browser_gpu(page):
    return page.evaluate(GPU_ASSERT_JS)


def ready_guard(text):
    """Add to a deterministic page's existing render-readiness promise."""
    script='<script>window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};window.__hf.buildReady.hardwareGpu=Promise.resolve().then(('+GPU_ASSERT_JS+'));</script>'
    return text.replace('</body>',script+'</body>')
