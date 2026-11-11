"""Shared GPU routing without changing model choices, edit plans or output formats."""
def speech_options(root):
    device = heavy_device(root)
    return {'device': device, 'compute_type': 'int8_float16' if device == 'cuda' else 'int8'}


def heavy_device(root, requested=None):
    """Owner GPU-only policy reroutes heavy CPU requests; small helpers are unaffected."""
    from .model_preferences import preferred_device, preferences
    policy=preferences(root)
    if policy.get('heavy_workloads_gpu_only'):
        return 'cuda'
    device=requested or preferred_device(root)
    h264_profile(device)
    return device


def h264_profile(device='cpu', quality=18):
    if device not in ('cpu', 'cuda'):
        raise ValueError('Choose CPU or NVIDIA GPU encoding.')
    if type(quality) is not int or not 0 <= quality <= 51:
        raise ValueError('Choose an H.264 quality from 0 to 51.')
    if device == 'cuda':
        return 'h264_nvenc', {'preset': 'p5', 'cq': str(quality), 'b': '0'}
    return 'libx264', {'preset': 'fast', 'crf': str(quality)}


def ffmpeg_h264(device='cpu', quality=18):
    codec, options = h264_profile(device, quality)
    result = ['-c:v', codec]
    for key, value in options.items():
        result.extend(['-b:v' if key == 'b' else '-' + key, value])
    return result


def hyperframes_flags(device='cpu'):
    h264_profile(device)
    return ['--gpu', '--browser-gpu'] if device == 'cuda' else ['--no-browser-gpu']


def require_gpu_implementation(root, feature, supported):
    """Stop before expensive software work when this machine requires GPU-only."""
    from .model_preferences import preferences
    if not supported and preferences(root).get('heavy_workloads_gpu_only'):
        raise RuntimeError(f'{feature} has no GPU implementation in this export path. CPU fallback is disabled. Your source and saved edit are kept; use an available GPU export or editable Adobe handoff.')
