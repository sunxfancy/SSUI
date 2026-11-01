"""Local CogVideoX-2B; original T5 is the quality-validated default.

The optional Int8 encoder saves VRAM but reduced motion in the measured A/B clip.
"""
from pathlib import Path
import torch
from ssui.annotation import param
from ssui.base import Image, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


class CogVideo2BModel:
    def __init__(self, pipeline=None):
        self.pipeline = pipeline

    @staticmethod
    def load(model_path: str, quantized_t5_path: str = '') -> 'CogVideo2BModel':
        from diffusers import CogVideoXPipeline, CogVideoXTransformer3DModel, AutoencoderKLCogVideoX
        options = {}
        if quantized_t5_path:
            import accelerate
            from transformers import AutoConfig, T5EncoderModel
            from safetensors.torch import load_file
            from backend.quantization.bnb_llm_int8 import quantize_model_llm_int8
            from backend.model_manager.load.model_loaders.flux import BnbQuantizedLlmInt8bCheckpointModel
            root = Path(quantized_t5_path) / 'text_encoder_2'
            with accelerate.init_empty_weights():
                encoder = T5EncoderModel(AutoConfig.from_pretrained(root, local_files_only=True))
                encoder = quantize_model_llm_int8(encoder, modules_to_not_convert=set())
            BnbQuantizedLlmInt8bCheckpointModel._load_state_dict_into_t5(
                encoder, load_file(root / 'bnb_llm_int8_model.safetensors'))
            options['text_encoder'] = encoder.eval().to(device='cuda', dtype=torch.float16)
        else:
            from transformers import T5EncoderModel
            # Stream original encoder shards directly to GPU instead of retaining
            # a 9.5 GB CPU parameter set until the entire pipeline has loaded.
            options['text_encoder'] = T5EncoderModel.from_pretrained(
                Path(model_path) / 'text_encoder', torch_dtype=torch.float16,
                device_map={'': 'cuda'}, low_cpu_mem_usage=True, local_files_only=True)
        for name, component in [('transformer', CogVideoXTransformer3DModel),
                                ('vae', AutoencoderKLCogVideoX)]:
            options[name] = component.from_pretrained(
                Path(model_path) / name, torch_dtype=torch.float16,
                device_map={'': 'cuda'}, low_cpu_mem_usage=True, local_files_only=True)
        pipeline = CogVideoXPipeline.from_pretrained(
            model_path, torch_dtype=torch.float16, local_files_only=True, **options).to('cuda')
        pipeline.vae.enable_slicing()
        pipeline.vae.enable_tiling()
        return CogVideo2BModel(pipeline)


@param('width', Slider(256, 720, 16), default=720)
@param('height', Slider(256, 480, 16), default=480)
@param('num_frames', Slider(5, 49, 4), default=49)
@param('num_inference_steps', Slider(1, 100, 1), default=50)
@param('seed', Random(), default=42)
def CogVideo2BTextToVideo(config: SSUIConfig, model: CogVideo2BModel,
                        prompt: Prompt, negative_prompt: Prompt) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    frames = int(config['num_frames'])
    if frames < 5 or (frames - 1) % 4:
        raise ValueError('CogVideoX frame count must be 4n+1, at least 5')
    result = model.pipeline(prompt=prompt.text, negative_prompt=negative_prompt.text,
                            height=config['height'], width=config['width'], num_frames=frames,
                            num_inference_steps=config['num_inference_steps'], guidance_scale=6.0,
                            generator=torch.Generator(device='cuda').manual_seed(int(config['seed'])))
    return [Image(frame) for frame in result.frames[0]]
