"""AI Images & Video worker. Runs inside the separate AI environment (tools/aigen/install/venv), never in the
editor's own Python. Reads a job list, writes each picture/clip, and prints one JSON line per event:

    python worker.py --jobs jobs.json --install D:/HinglishEditorModels

Models: Z-Image Turbo (pictures, 9 steps) and Wan 2.2 TI2V 5B (720p 24 fps clips, from text or from a picture).
Memory mode from the GPU: full (22 GB+), offload (11-22 GB: fp8 weights + one model on the GPU at a time),
low (under 11 GB: layer by layer from system memory; slow, small pictures and short clips)."""
import argparse
import gc
import json
import sys
import time
import traceback
from pathlib import Path

IMAGE_REPO = 'Tongyi-MAI--Z-Image-Turbo'
VIDEO_REPO = 'Wan-AI--Wan2.2-TI2V-5B-Diffusers'
IMAGE_STEPS = 9
VIDEO_STEPS = {'full': 40, 'offload': 30, 'low': 20}


def say(**event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def gpu_facts(torch):
    if not torch.cuda.is_available():
        return '', 0.0
    props = torch.cuda.get_device_properties(0)
    return props.name, round(props.total_memory / 2 ** 30, 1)


def memory_mode(vram, wanted='auto'):
    if wanted != 'auto':
        return wanted
    if vram >= 22:
        return 'full'
    if vram >= 11:
        return 'offload'
    return 'low'


def place(pipe, mode, torch, fp8_parts=('transformer',)):
    """Put a pipeline on the GPU the way this card can hold it."""
    if mode in ('offload', 'low'):
        for name in fp8_parts:
            part = getattr(pipe, name, None)
            if part is not None and hasattr(part, 'enable_layerwise_casting'):
                try:     # weights kept in 8 bits, maths in bf16: half the memory, nearly the same picture
                    part.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=torch.bfloat16)
                except Exception as error:
                    say(event='note', text=f'8-bit weights not available for {name}: {error}')
    if mode == 'full':
        pipe.to('cuda')
    elif mode == 'offload':
        pipe.enable_model_cpu_offload()
    else:
        pipe.enable_sequential_cpu_offload()
    vae = getattr(pipe, 'vae', None)
    for switch in ('enable_tiling', 'enable_slicing'):
        if vae is not None and hasattr(vae, switch):
            try:
                getattr(vae, switch)()
            except Exception:
                pass
    return pipe


def free(torch):
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def progress(item_id, steps):
    def callback(pipe, step, timestep, kwargs):
        say(event='step', id=item_id, step=step + 1, steps=steps)
        return kwargs
    return callback


def encode_image_prompts(items, path, mode, torch, options):
    """Release the 4B text encoder before loading the image transformer on small laptops."""
    from diffusers import FlowMatchEulerDiscreteScheduler, ZImagePipeline
    from transformers import AutoModel, AutoTokenizer
    say(event='loading', model='Z-Image text encoder', mode=mode)
    tokenizer = AutoTokenizer.from_pretrained(str(path), subfolder='tokenizer', local_files_only=True)
    encoder = AutoModel.from_pretrained(str(path), subfolder='text_encoder',
        torch_dtype=torch.bfloat16, local_files_only=True, **options)
    device = 'cuda' if mode == 'offload' else 'cpu'
    encoder.to(device)
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(str(path), subfolder='scheduler')
    reader = ZImagePipeline(tokenizer=tokenizer, text_encoder=encoder, vae=None,
                           transformer=None, scheduler=scheduler)
    embeds = {}
    with torch.no_grad():
        for item in items:
            positive, _ = reader.encode_prompt(item['prompt'], device=torch.device(device),
                                               do_classifier_free_guidance=False)
            embeds[item['id']] = [value.cpu() for value in positive]
    del reader, encoder
    free(torch)
    return embeds


def run_images(items, models, mode, torch):
    from diffusers import ZImagePipeline
    say(event='loading', model='Z-Image Turbo', mode=mode)
    path = models / IMAGE_REPO
    options = {'variant': 'bf16'} if (path / 'transformer/diffusion_pytorch_model.safetensors.index.bf16.json').is_file() else {}
    embeds = encode_image_prompts(items, path, mode, torch, options) if mode != 'full' else None
    components = {'text_encoder': None, 'tokenizer': None} if embeds is not None else {}
    pipe = ZImagePipeline.from_pretrained(str(path), torch_dtype=torch.bfloat16, **components, **options)
    place(pipe, mode, torch)
    for item in items:
        started = time.time()
        try:
            width, height = item['width'], item['height']
            if mode == 'low':          # the test mode keeps pictures small
                scale = min(1.0, (640 * 640 / (width * height)) ** .5)
                width, height = int(width * scale) // 16 * 16, int(height * scale) // 16 * 16
            prompt = {'prompt': item['prompt']} if embeds is None else {
                'prompt_embeds': [value.to('cuda') for value in embeds[item['id']]]}
            image = pipe(**prompt, height=height, width=width, num_inference_steps=IMAGE_STEPS,
                         guidance_scale=0.0, generator=torch.Generator('cpu').manual_seed(int(item['seed'])),
                         callback_on_step_end=progress(item['id'], IMAGE_STEPS)).images[0]
            Path(item['out']).parent.mkdir(parents=True, exist_ok=True)
            image.save(item['out'])
            say(event='done', id=item['id'], out=item['out'], seconds=round(time.time() - started, 1),
                width=image.width, height=image.height)
        except Exception as error:
            say(event='error', id=item['id'], error=f'{type(error).__name__}: {error}'[:500], trace=traceback.format_exc()[-2500:])
            free(torch)
    del pipe
    free(torch)


def encode_video_prompts(items, path, mode, torch):
    """Stage 1 of 2: only the text encoder (UMT5-XXL, ~11 GB) is loaded, every prompt becomes numbers, then it is
    freed. Loading it together with the video model needed ~21 GB of system memory; one at a time needs ~11 GB."""
    from diffusers import FlowMatchEulerDiscreteScheduler, WanPipeline
    from transformers import AutoTokenizer, UMT5EncoderModel
    say(event='loading', model='Wan 2.2 text encoder', mode=mode)
    tokenizer = AutoTokenizer.from_pretrained(path, subfolder='tokenizer')
    encoder = UMT5EncoderModel.from_pretrained(path, subfolder='text_encoder', torch_dtype=torch.bfloat16)
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(path, subfolder='scheduler')
    device = 'cuda' if mode == 'full' else 'cpu'       # 11 GB would not fit next to anything else on 12 GB
    encoder.to(device)
    reader = WanPipeline(tokenizer=tokenizer, text_encoder=encoder, vae=None, scheduler=scheduler)
    embeds = {}
    with torch.no_grad():
        for item in items:
            positive, negative = reader.encode_prompt(item['prompt'], item.get('negative', ''),
                                                      do_classifier_free_guidance=True, device=torch.device(device),
                                                      dtype=torch.bfloat16)
            embeds[item['id']] = (positive.cpu(), negative.cpu())
    del reader, encoder
    free(torch)
    return embeds


def run_videos(items, models, mode, torch):
    from diffusers import AutoencoderKLWan, WanPipeline, WanTransformer3DModel
    from diffusers.utils import export_to_video
    path = str(models / VIDEO_REPO)
    embeds = encode_video_prompts(items, path, mode, torch)
    say(event='loading', model='Wan 2.2 5B', mode=mode)
    # bf16 like the rest of the model (also saves memory on 12 GB cards)
    vae = AutoencoderKLWan.from_pretrained(path, subfolder='vae', torch_dtype=torch.bfloat16)
    compact=mode in ('offload','low')
    transformer=None
    if compact:
        # Loading the full bf16 transformer before reducing it to fp8 creates
        # a large RAM spike on 16 GB Windows machines. Load its storage dtype
        # directly; restore sensitive unhooked modules before bf16 computation.
        say(event='loading',model='Wan compact transformer storage',mode=mode)
        # The Windows crash receipt pinpoints safetensors' mapped-storage
        # reader. Use Diffusers' supported non-mapped loader on that platform.
        transformer=WanTransformer3DModel.from_pretrained(path,subfolder='transformer',torch_dtype=torch.float8_e4m3fn,
            low_cpu_mem_usage=True,disable_mmap=sys.platform=='win32')
        from diffusers.hooks.layerwise_casting import DEFAULT_SKIP_MODULES_PATTERN
        patterns=tuple(DEFAULT_SKIP_MODULES_PATTERN)+tuple(transformer._skip_layerwise_casting_patterns or ())+tuple(transformer._keep_in_fp32_modules or ())
        import re
        for name,module in transformer.named_modules():
            if any(re.search(pattern,name) for pattern in patterns):
                for param in module.parameters(recurse=False):
                    if param.dtype==torch.float8_e4m3fn:param.data=param.data.to(torch.bfloat16)
        transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn,compute_dtype=torch.bfloat16)
    pipe = WanPipeline.from_pretrained(path, vae=vae, text_encoder=None, tokenizer=None, torch_dtype=torch.bfloat16,
        **({'transformer':transformer} if transformer is not None else {}))
    animate = None
    if any(item.get('image') for item in items):
        from diffusers import WanImageToVideoPipeline
        # Share the loaded components without widening compact fp8 storage.
        # Install offload hooks on the actual image-to-video pipeline afterward.
        animate=WanImageToVideoPipeline.from_pipe(pipe,torch_dtype=None)
    place(animate or pipe, mode, torch,fp8_parts=() if compact else ('transformer',))
    steps = VIDEO_STEPS[mode]
    for item in items:
        started = time.time()
        try:
            width, height, frames = item['width'], item['height'], item['frames']
            if mode == 'low':          # test mode: 480p, 2 seconds
                width, height = (480,480) if width==height else (832,480) if width>height else (480,832)
                frames = min(frames, 49)
            positive, negative = embeds[item['id']]
            # Diffusers preserves the device of supplied embeddings. Wan's
            # conditioning block follows that device, so staged CPU embeddings
            # must join the transformer on CUDA before denoising.
            options = dict(prompt_embeds=positive.to('cuda'), negative_prompt_embeds=negative.to('cuda'), height=height, width=width,
                           num_frames=frames, guidance_scale=5.0, num_inference_steps=steps,
                           generator=torch.Generator('cpu').manual_seed(int(item['seed'])),
                           callback_on_step_end=progress(item['id'], steps))
            if item.get('image'):
                from PIL import Image
                picture = Image.open(item['image']).convert('RGB').resize((width, height))
                result = animate(image=picture, **options)
            else:
                result = pipe(**options)
            Path(item['out']).parent.mkdir(parents=True, exist_ok=True)
            export_to_video(result.frames[0], item['out'], fps=item.get('fps', 24))
            say(event='done', id=item['id'], out=item['out'], seconds=round(time.time() - started, 1),
                width=width, height=height, frames=frames)
        except Exception as error:
            say(event='error', id=item['id'], error=f'{type(error).__name__}: {error}'[:500], trace=traceback.format_exc()[-2500:])
            free(torch)
    del pipe, animate
    free(torch)


def complete_weight(path):
    """Check declared safetensors extent without loading the tensor data."""
    try:
        with path.open('rb') as source:
            length = int.from_bytes(source.read(8), 'little')
            size = path.stat().st_size
            if not 0 < length <= 16 * 1024 * 1024 or length + 8 > size:
                return False
            header = json.loads(source.read(length))
        tensors = [value for key, value in header.items() if key != '__metadata__']
        offsets = [value['data_offsets'] for value in tensors]
        return bool(offsets) and all(0 <= a <= b for a, b in offsets) and 8 + length + max(b for a, b in offsets) == size
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def complete(folder):
    """Check every required component and indexed shard before reporting ready."""
    folder = Path(folder)
    try:
        model = json.loads((folder / 'model_index.json').read_text(encoding='utf-8'))
        if not (folder / 'scheduler/scheduler_config.json').is_file():
            return False
        tokenizer = folder / 'tokenizer'
        if not (tokenizer / 'tokenizer_config.json').is_file() or not any(
                (tokenizer / name).is_file() for name in ('tokenizer.json', 'spiece.model', 'vocab.json')):
            return False
        tokenizer_config = json.loads((tokenizer / 'tokenizer_config.json').read_text(encoding='utf-8'))
        if model.get('_class_name') == 'ZImagePipeline' and not tokenizer_config.get('chat_template'):
            template = tokenizer / 'chat_template.jinja'
            if not template.is_file() or not template.read_text(encoding='utf-8').strip():
                return False
        if any((folder / '.cache').rglob('*.incomplete')):
            return False
        variant = '.bf16' if (folder / 'transformer/diffusion_pytorch_model.safetensors.index.bf16.json').is_file() else ''
        for component in ('text_encoder', 'transformer', 'vae', 'transformer_2'):
            if component == 'transformer_2' and model.get(component) in (None, [None, None]):
                continue
            if model.get(component) in (None, [None, None]):
                return False
            path = folder / component
            if not (path / 'config.json').is_file():
                return False
            prefix = 'model' if component == 'text_encoder' else 'diffusion_pytorch_model'
            index = path / (prefix + '.safetensors.index' + variant + '.json')
            if index.is_file():
                mapping = json.loads(index.read_text(encoding='utf-8'))['weight_map']
                names = set(mapping.values())
                if not names or any(not isinstance(name, str) or Path(name).name != name for name in names):
                    return False
                weights = [path / name for name in names]
            else:
                weights = [path / (prefix + variant + '.safetensors')]
            if not all(complete_weight(weight) for weight in weights):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def doctor(install):
    """What is installed and how this GPU will run it (printed as one JSON line)."""
    import torch
    name, vram = gpu_facts(torch)
    models = Path(install) / 'models'
    say(event='doctor', gpu=name, vram_gb=vram, cuda=torch.cuda.is_available(), mode=memory_mode(vram),
        image_model=complete(models / IMAGE_REPO), video_model=complete(models / VIDEO_REPO))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', required=True)
    parser.add_argument('--jobs')
    parser.add_argument('--mode', default='auto', choices=['auto', 'full', 'offload', 'low'])
    parser.add_argument('--doctor', action='store_true')
    args = parser.parse_args()
    if args.doctor:
        doctor(args.install)
        return 0
    import torch
    name, vram = gpu_facts(torch)
    if not name:
        say(event='fatal', error='No NVIDIA GPU is visible to PyTorch')
        return 2
    mode = memory_mode(vram, args.mode)
    say(event='start', gpu=name, vram_gb=vram, mode=mode)
    jobs = json.loads(Path(args.jobs).read_text(encoding='utf-8'))
    models = Path(args.install) / 'models'
    images = [i for i in jobs['items'] if i['kind'] == 'image']
    videos = [i for i in jobs['items'] if i['kind'] == 'video']
    try:
        if images:
            run_images(images, models, mode, torch)
        if videos:
            run_videos(videos, models, mode, torch)
    except Exception as error:
        say(event='fatal', error=f'{type(error).__name__}: {error}'[:800], trace=traceback.format_exc()[-1500:])
        return 1
    say(event='finished')
    return 0


if __name__ == '__main__':
    sys.exit(main())
