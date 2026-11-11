"""Bounded CUDA frame operations. No model load, batch cache or CPU fallback.

CPU media decoding and final host transfer are I/O support. Scaling, sampling,
blur, tint, scanlines and alpha blending execute on CUDA tensors.
"""
import math
from functools import wraps
from inspect import signature


def with_cuda_frames(function):
    """Own one small frame processor for the render, released even after failure."""
    spec = signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = spec.bind_partial(*args, **kwargs)
        processor = CudaFrames() if bound.arguments.get('device', 'cpu') == 'cuda' else None
        kwargs['_gpu'] = processor
        try: return function(*args, **kwargs)
        finally:
            if processor is not None: processor.close()
    return wrapped


def zoom_box(width, height, zoom, dx=0., dy=0.):
    if not all(math.isfinite(v) for v in (width, height, zoom, dx, dy)) or min(width, height, zoom) <= 0:
        raise ValueError('Frame dimensions and zoom must be positive finite values.')
    w, h = width / zoom, height / zoom
    return ((width-w)/2+dx, (height-h)/2+dy, (width+w)/2+dx, (height+h)/2+dy)


class CudaFrames:
    def __init__(self):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('NVIDIA frame processing is unavailable; CPU fallback is disabled. Keep the saved edit and retry when CUDA is available.')
        self.torch = torch
        self.device = 'cuda'
        self._grid_size = None
        self._axes = None
        self._kernels = {}

    def upload(self, pixels):
        import numpy as np
        array=np.ascontiguousarray(pixels)
        if not array.flags.writeable:array=array.copy()
        t = self.torch.as_tensor(array, device=self.device)
        if t.ndim != 3 or t.shape[-1] not in (3, 4):
            raise ValueError('GPU frames require RGB or RGBA pixels.')
        return t.permute(2, 0, 1).unsqueeze(0).float()

    def download(self, tensor):
        return tensor.squeeze(0).permute(1, 2, 0).clamp(0, 255).round().to(self.torch.uint8).cpu().numpy()

    def blank(self, width, height):
        return self.torch.zeros((1, 3, height, width), device=self.device)

    def resize(self, tensor, width, height, mode='bilinear'):
        if tensor.shape[-2:] == (height, width): return tensor
        from torch.nn.functional import interpolate
        return interpolate(tensor, size=(height, width), mode=mode,
                           **({'align_corners': False, 'antialias': True} if mode in ('bilinear', 'bicubic') else {}))

    def fit(self, tensor, width, height, fill=False):
        sh, sw = tensor.shape[-2:]
        scale = (max if fill else min)(width/sw, height/sh)
        fw, fh = max(1, round(sw*scale)), max(1, round(sh*scale))
        image = self.resize(tensor, fw, fh, 'bicubic')
        if fill:
            x, y = (fw-width)//2, (fh-height)//2
            return image[..., y:y+height, x:x+width]
        canvas = self.blank(width, height)
        x, y = (width-fw)//2, (height-fh)//2
        canvas[..., y:y+fh, x:x+fw] = image[:, :3]
        return canvas

    def crop(self, tensor, box, width, height, mode='bilinear'):
        """Box uses pixel edges, matching Pillow resize(box=...) coordinates."""
        from torch.nn.functional import grid_sample
        t = self.torch
        sh, sw = tensor.shape[-2:]
        x0, y0, x1, y1 = box
        if not all(math.isfinite(v) for v in box) or x1 <= x0 or y1 <= y0:
            raise ValueError('GPU crop region is invalid.')
        # Antialias downsampling before subpixel sampling, preserving pixel-edge
        # coordinates. Avoid shimmer when reducing large source footage.
        scale=min(1.,width/(x1-x0),height/(y1-y0))
        if scale < .999:
            nw,nh=max(1,round(sw*scale)),max(1,round(sh*scale))
            tensor=self.resize(tensor,nw,nh,'bicubic')
            x0,x1=x0*nw/sw,x1*nw/sw
            y0,y1=y0*nh/sh,y1*nh/sh
            sw,sh=nw,nh
        if self._grid_size != (width, height):
            self._axes = t.meshgrid((t.arange(height, device=self.device)+.5)/height,
                                   (t.arange(width, device=self.device)+.5)/width, indexing='ij')
            self._grid_size = (width, height)
        ys, xs = self._axes
        grid = t.stack((2*(x0+xs*(x1-x0))/sw-1, 2*(y0+ys*(y1-y0))/sh-1), -1).unsqueeze(0)
        return grid_sample(tensor, grid, mode=mode, padding_mode='zeros', align_corners=False)

    def over(self, base, foreground):
        """Blend straight RGBA, retaining RGB output. Scale premultiplied color."""
        h, w = base.shape[-2:]
        if foreground.shape[1] == 3: return self.resize(foreground, w, h)
        alpha = foreground[:, 3:4].clamp(0, 255)/255
        color = self.resize(foreground[:, :3]*alpha, w, h)
        alpha = self.resize(alpha, w, h)
        return color+base*(1-alpha)

    def blur(self, tensor, sigma):
        from torch.nn.functional import conv2d, pad
        channels = tensor.shape[1]
        key = (sigma, channels)
        if key not in self._kernels:
            radius = math.ceil(sigma*3)
            xs = self.torch.arange(-radius, radius+1, device=self.device, dtype=tensor.dtype)
            kernel = self.torch.exp(-xs.square()/(2*sigma*sigma)); kernel /= kernel.sum()
            self._kernels[key] = (kernel.view(1, 1, 1, -1).repeat(channels, 1, 1, 1), radius)
        kernel, r = self._kernels[key]
        image = conv2d(pad(tensor, (r, r, 0, 0), mode='reflect'), kernel, groups=channels)
        return conv2d(pad(image, (0, 0, r, r), mode='reflect'), kernel.transpose(2, 3), groups=channels)

    def fit_pixels(self, pixels, width, height):
        return self.download(self.fit(self.upload(pixels), width, height))

    def video_frame(self, tensor):
        """BT.601 limited-range YUV420 conversion on CUDA; host copy is I/O only."""
        import av
        import numpy as np
        from torch.nn.functional import avg_pool2d
        h, w = tensor.shape[-2:]
        if h % 2 or w % 2: raise ValueError('GPU video encoding requires even dimensions.')
        rgb = tensor[:, :3].clamp(0, 255)
        r, g, b = rgb[:, 0:1], rgb[:, 1:2], rgb[:, 2:3]
        y = 16+(65.738*r+129.057*g+25.064*b)/256
        half = avg_pool2d(rgb, 2, 2)
        r, g, b = half[:, 0:1], half[:, 1:2], half[:, 2:3]
        u = 128+(-37.945*r-74.494*g+112.439*b)/256
        v = 128+(112.439*r-94.154*g-18.285*b)/256
        frame = av.VideoFrame(w, h, 'yuv420p')
        for plane, values in zip(frame.planes, (y, u, v)):
            array = values.squeeze(0).squeeze(0).clamp(0, 255).round().to(self.torch.uint8).cpu().numpy()
            if plane.line_size != array.shape[1]:
                padded = np.zeros((array.shape[0], plane.line_size), dtype=np.uint8)
                padded[:, :array.shape[1]] = array
                array = padded
            plane.update(array.tobytes())
        return frame

    def close(self):
        self._axes = None
        self._kernels.clear()
        # Release only unused allocator blocks, never another model's live tensors.
        self.torch.cuda.empty_cache()
