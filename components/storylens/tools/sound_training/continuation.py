"""Continue an isolated LoRA without erasing its earlier learned parameters."""
import hashlib
import json
from pathlib import Path


def validate_parent(parent, output, base, rank, alpha):
    parent=Path(parent).resolve(); output=Path(output).resolve()
    if output==parent or output in parent.parents or parent in output.parents:
        raise ValueError('Parent adapter and continuation output must be separate')
    config=json.loads((parent/'adapter_config.json').read_text(encoding='utf-8'))
    if (Path(config['base_model_name_or_path']).resolve()!=Path(base).resolve()
        or config.get('peft_type')!='LORA' or config.get('r')!=rank
        or config.get('lora_alpha')!=alpha or config.get('bias')!='none'
        or set(config.get('target_modules',[]))!={'q_proj','k_proj','v_proj','o_proj'}
        or config.get('use_dora',False) or config.get('use_rslora',False)
        or config.get('modules_to_save') or config.get('rank_pattern') or config.get('alpha_pattern')):
        raise ValueError('Parent adapter does not match the pinned training architecture')
    weights=parent/'adapter_model.safetensors'
    with weights.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(parent),sha256=digest,optimizer_resumed=False,
                method='Continue saved LoRA weights with a fresh optimizer; previous adapter preserved')


def validate_weights(expected, supplied):
    import torch
    if set(expected)!=set(supplied) or not supplied:
        raise ValueError('Parent adapter tensor names are incomplete or unexpected')
    for name,value in supplied.items():
        if ('lora_' not in name or value.shape!=expected[name].shape
            or not value.is_floating_point() or not bool(torch.isfinite(value).all())):
            raise ValueError('Invalid parent adapter tensor: '+name)


def load_parent(model, parent):
    from safetensors.torch import load_file
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    import torch
    expected=get_peft_model_state_dict(model)
    supplied=load_file(str(Path(parent)/'adapter_model.safetensors'),device='cpu')
    validate_weights(expected,supplied)
    result=set_peft_model_state_dict(model,supplied)
    if result.unexpected_keys or any('lora_' in name for name in result.missing_keys):
        raise ValueError('The complete parent adapter was not loaded')
    actual=get_peft_model_state_dict(model)
    for name,value in supplied.items():
        if not torch.equal(actual[name].detach().cpu(),value.to(dtype=actual[name].dtype)):
            raise ValueError('Parent parameter did not survive loading: '+name)
    return len(supplied)
