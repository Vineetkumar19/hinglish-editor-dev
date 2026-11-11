"""This process owns the model lifetime. No model is imported by the web service."""
import json
from pathlib import Path
import sys


def gpu_config(torch, device='cuda'):
    """CUDA stays the default; CPU requires an explicit task-level request."""
    if device == 'cpu': return 'cpu', torch.float32
    if device != 'cuda': raise ValueError('Voiceover device: choose CUDA or an explicitly requested CPU generation.')
    if not torch.cuda.is_available():
        raise RuntimeError('Voiceover GPU: NVIDIA CUDA is unavailable. Check the NVIDIA driver and GPU runtime, then retry. CPU fallback is disabled.')
    return 'cuda', torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32


def main():
    task = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    sys.path.insert(0, task['source'])
    import torch
    device, dtype = gpu_config(torch, task.get('device','cuda'))
    import soundfile as sf
    from omnivoice import OmniVoice
    torch.set_num_threads(4)
    model = OmniVoice.from_pretrained(task['model'], device_map=device, dtype=dtype, load_asr=False)
    # Saved references are validated mono PCM. Passing a waveform avoids
    # torchaudio 2.9's TorchCodec/FFmpeg DLL dependency on Windows.
    samples, sample_rate = sf.read(task['reference'], dtype='float32')
    reference = (torch.from_numpy(samples).reshape(1,-1), sample_rate)
    with torch.inference_mode():
        audio = model.generate(text=task.get('spoken_script',task['script']), ref_audio=reference,
                               ref_text=task.get('spoken_reference',task['transcript']), language=None if task['language']=='auto' else task['language'],
                               speed=task['speed'], num_step=32)[0]
    sf.write(task['output'], audio.detach().float().cpu().reshape(-1).numpy(), model.sampling_rate, subtype='PCM_16')
    print(json.dumps({'engine':'VoiceStudio · OmniVoice','device':device,'gpu':torch.cuda.get_device_name() if device=='cuda' else None,
                      'characters':len(task['script']),'sample_rate':model.sampling_rate}))


if __name__ == '__main__': main()
