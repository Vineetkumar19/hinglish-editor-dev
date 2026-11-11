"""Exercise staged image encoding and GPU offload with tiny random weights.

This checks library compatibility only, never model quality or full-model fit.
"""
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/aigen'))


def main():
    import torch
    from diffusers import (AutoencoderKL, AutoencoderKLWan, FlowMatchEulerDiscreteScheduler,
        ZImagePipeline, ZImageTransformer2DModel, WanPipeline, WanTransformer3DModel)
    from transformers import AutoTokenizer, Qwen3Config, Qwen3Model, UMT5Config, UMT5EncoderModel
    import worker
    from PIL import Image

    torch.set_num_threads(4)
    torch.manual_seed(7)
    folder = ROOT / 'output/validation/new-laptop' / ('api-control-' + uuid.uuid4().hex[:10])
    model = folder / worker.IMAGE_REPO
    tokenizer = AutoTokenizer.from_pretrained(ROOT / 'tools/aigen/install/models' / worker.IMAGE_REPO / 'tokenizer', local_files_only=True)
    encoder = Qwen3Model(Qwen3Config(vocab_size=len(tokenizer), hidden_size=32,
        intermediate_size=64, num_hidden_layers=2, num_attention_heads=2,
        num_key_value_heads=2, head_dim=16)).to(torch.bfloat16)
    transformer = ZImageTransformer2DModel(in_channels=4, dim=32, n_layers=1,
        n_refiner_layers=1, n_heads=2, n_kv_heads=2, cap_feat_dim=32,
        axes_dims=[4, 6, 6], axes_lens=[1024, 512, 512]).to(torch.bfloat16)
    vae = AutoencoderKL(in_channels=3, out_channels=3,
        down_block_types=('DownEncoderBlock2D',) * 4,
        up_block_types=('UpDecoderBlock2D',) * 4,
        block_out_channels=(8, 8, 8, 8), layers_per_block=1,
        latent_channels=4, norm_num_groups=4, shift_factor=0.0,
        scaling_factor=1.0).to(torch.bfloat16)
    pipe = ZImagePipeline(scheduler=FlowMatchEulerDiscreteScheduler(), vae=vae,
        tokenizer=tokenizer, text_encoder=encoder, transformer=transformer)
    pipe.save_pretrained(model)
    del pipe, encoder, transformer, vae
    worker.free(torch)
    item = dict(id='tiny-api-control', prompt='A red mug.', width=64, height=64,
                seed=7, out=str(folder / 'random-api-control.png'))
    worker.IMAGE_STEPS = 2
    worker.run_images([item], folder, 'offload', torch)
    with Image.open(item['out']) as image:
        assert image.size == (64, 64)
        image.verify()
    video_model = folder / worker.VIDEO_REPO
    encoder = UMT5EncoderModel(UMT5Config(vocab_size=len(tokenizer), d_model=32,
        d_kv=8, d_ff=64, num_layers=1, num_heads=4)).to(torch.bfloat16)
    transformer = WanTransformer3DModel(in_channels=4, out_channels=4, text_dim=32,
        num_attention_heads=2, attention_head_dim=16, freq_dim=32,
        ffn_dim=64, num_layers=1).to(torch.bfloat16)
    vae = AutoencoderKLWan(base_dim=16, decoder_base_dim=16, z_dim=4,
        dim_mult=[1, 1, 1, 1], num_res_blocks=1,
        latents_mean=[0.0]*4, latents_std=[1.0]*4).to(torch.bfloat16)
    pipe = WanPipeline(tokenizer=tokenizer, text_encoder=encoder, transformer=transformer,
                       vae=vae, scheduler=FlowMatchEulerDiscreteScheduler(), expand_timesteps=True)
    pipe.save_pretrained(video_model)
    del pipe, encoder, transformer, vae
    worker.free(torch)
    clip = dict(id='tiny-video-api-control', prompt='A ball.', negative='', width=64,
                height=64, frames=5, fps=8, seed=7, out=str(folder/'random-api-control.mp4'))
    animated = dict(clip, id='tiny-image-to-video-api-control', image=item['out'],
                    out=str(folder/'random-image-to-video-api-control.mp4'))
    worker.VIDEO_STEPS['offload'] = 2
    worker.run_videos([clip, animated], folder, 'offload', torch)
    import imageio.v2 as imageio
    for control in (clip, animated):
        with imageio.get_reader(control['out'], format='ffmpeg') as video:
            assert video.get_meta_data()['size'] == (64, 64)
            assert sum(1 for _ in video) == 5
    receipt = dict(passed=True, scope='Tiny random weights: staged encoding and GPU offload API compatibility only.',
                   image=item['out'], video=clip['out'], image_to_video=animated['out'])
    (ROOT / 'output/validation/new-laptop/generation-api-control.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
