"""Local MOSS inference using the existing Torch 2.4 / Transformers 4 runtime."""
from pathlib import Path
from threading import RLock

import torch

from .dit import MOSSImageDiT, validate_skip_layers
from .text_encoder import TextEncoder
from .vae import Flux2VAE
from .weights import load_component, read_config, text_weight_key


def sampling_sigmas(steps, shift, training_steps=1000, training_shift=1.0):
    if type(steps) is not int or steps < 1:
        raise ValueError("steps must be a positive integer")
    if not 0 < shift < float("inf"):
        raise ValueError("shift must be finite and positive")
    if not 0 < training_shift < float("inf") or type(training_steps) is not int or training_steps < 2:
        raise ValueError("Invalid training sigma grid")
    # Official V2 schedule: shifted grid snapped to the nearest training sigma.
    # This differs from a plain linspace Euler schedule, including its final step.
    def grid(count, amount):
        lower = amount / (training_steps + amount - 1)
        values = torch.linspace(1, lower, count, dtype=torch.float32)
        return amount * values / (1 + (amount - 1) * values)
    sigmas = grid(steps, shift)
    training = grid(training_steps, training_shift).flip(0)
    upper = torch.searchsorted(training, sigmas).clamp(max=training_steps - 1)
    lower = (upper - 1).clamp(min=0)
    nearest = torch.where((sigmas - training[lower]).abs() <= (training[upper] - sigmas).abs(), lower, upper)
    return torch.cat((torch.unique_consecutive(training[nearest]), torch.zeros(1)))


def format_prompt(prompt):
    if not isinstance(prompt, str):
        raise ValueError("MOSS prompt must be a string")
    return f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n"


class MOSSPipeline:
    def __init__(self, transformer, text_encoder, vae, tokenizer, device="cpu", cpu_offload=True,
                 training_steps=1000, training_shift=1.0):
        self.transformer = transformer
        self.text_encoder = text_encoder
        self.vae = vae
        self.tokenizer = tokenizer
        self.device = torch.device(device)
        self.cpu_offload = cpu_offload
        self.training_steps = training_steps
        self.training_shift = training_shift
        # Component placement and inference share mutable module state.
        self.lock = RLock()

    @classmethod
    def from_pretrained(cls, model_path, device="cpu", cpu_offload=True, revision=None):
        from accelerate import init_empty_weights
        from transformers import PreTrainedTokenizerFast

        root = Path(model_path).expanduser()
        if not root.is_dir():
            if root.is_absolute() or str(model_path).startswith((".", "~")):
                raise FileNotFoundError(root)
            from huggingface_hub import snapshot_download
            root = Path(snapshot_download(
                model_path, revision=revision,
                allow_patterns=["*/config.json", "scheduler/scheduler_config.json", "tokenizer/*",
                                "*/*.safetensors", "*/*.safetensors.index.json"],
            ))
        dtype = torch.float32 if torch.device(device).type == "cpu" else torch.bfloat16
        dit_config = read_config(root / "transformer")
        if dit_config.get("_class_name") not in ("MOSSImageTransformer", "MOSImageTransformer"):
            raise ValueError("Expected a MOSS-Image transformer bundle")
        dit_keys = ("dim", "ffn_dim", "num_heads", "num_layers", "text_dim", "freq_dim", "latent_channels", "rope_base")
        te_config = read_config(root / "text_encoder")
        if te_config.get("model_type") not in ("qwen3_5", "qwen3_5_text"):
            raise ValueError("Expected a Qwen3.5 text encoder")
        vae_config = read_config(root / "vae")
        if vae_config.get("_class_name") != "AutoencoderKLFlux2":
            raise ValueError("Expected an AutoencoderKLFlux2 VAE")
        if vae_config.get("batch_norm_eps", 1e-4) != 1e-4 or vae_config.get("act_fn", "silu") != "silu":
            raise ValueError("Unsupported FLUX.2 VAE normalization or activation")
        vae_keys = ("in_channels", "out_channels", "latent_channels", "block_out_channels", "decoder_block_out_channels",
                    "layers_per_block", "patch_size", "use_quant_conv", "use_post_quant_conv", "mid_block_add_attention")
        kwargs = {k: vae_config[k] for k in vae_keys if k in vae_config}
        kwargs["num_groups"] = vae_config.get("norm_num_groups", 32)
        # No Transformers model loading and no trust_remote_code: implementations
        # live in backend/moss_image. Build parameters on meta before shard loads.
        with init_empty_weights():
            transformer = MOSSImageDiT(**{k: dit_config[k] for k in dit_keys if k in dit_config})
            text_encoder = TextEncoder(te_config)
            vae = Flux2VAE(**kwargs)
        load_component(transformer, root / "transformer", "diffusion_pytorch_model", dtype)
        load_component(text_encoder, root / "text_encoder", "model", dtype, text_weight_key)
        load_component(vae, root / "vae", "diffusion_pytorch_model", torch.float32)
        if transformer.text_dim != text_encoder.config.hidden_size or transformer.latent_channels != vae.num_latent_channels:
            raise ValueError("MOSS components have incompatible text or latent dimensions")
        # Read tokenizer.json directly: newer bundles may name a tokenizer class
        # unknown to Transformers 4. The actual tokenizer runs in tokenizers.
        tokenizer = PreTrainedTokenizerFast(
            tokenizer_file=str(root / "tokenizer" / "tokenizer.json"),
            eos_token="<|im_end|>", pad_token="<|im_end|>",
        )
        import json
        scheduler_path = root / "scheduler" / "scheduler_config.json"
        scheduler = json.loads(scheduler_path.read_text(encoding="utf-8")) if scheduler_path.is_file() else {}
        if scheduler.get("_class_name", "MOSSImageScheduler") != "MOSSImageScheduler":
            raise ValueError("Expected a MOSSImageScheduler")
        pipe = cls(transformer, text_encoder, vae, tokenizer, device, cpu_offload,
                   scheduler.get("num_train_timesteps", 1000), scheduler.get("training_shift", 1.0))
        if not cpu_offload:
            for model in (transformer, text_encoder, vae):
                model.to(device)
        return pipe

    def _encode(self, prompt, max_sequence_length):
        # Official MOSS Qwen3.5 chat template, including the thinking prefix.
        text = format_prompt(prompt)
        tokens = self.tokenizer(text, return_tensors="pt", add_special_tokens=False,
                                truncation=True, max_length=max_sequence_length)
        ids = tokens["input_ids"].to(self.device)
        mask = tokens["attention_mask"].to(self.device)
        return self.text_encoder(ids, mask), mask.bool()

    @torch.inference_mode()
    def __call__(self, prompt, negative_prompt="", width=1024, height=1024,
                 steps=50, guidance=3.0, shift=5.0, seed=42, max_sequence_length=4096,
                 uncond_skip_layers=(22,)):
        from PIL import Image

        if any(type(n) is not int or n < 16 or n % 16 for n in (width, height)):
            raise ValueError("Image dimensions must be positive multiples of 16")
        if not 1 <= max_sequence_length <= 4096:
            raise ValueError("max_sequence_length must be in [1, 4096]")
        if not 0 <= guidance < float("inf"):
            raise ValueError("guidance must be finite and nonnegative")
        skip = validate_skip_layers(uncond_skip_layers, len(self.transformer.layers))
        sigmas = sampling_sigmas(steps, shift, self.training_steps, self.training_shift).to(self.device)
        with self.lock:
            try:
                self.text_encoder.to(self.device)
                positive, mask = self._encode(prompt, max_sequence_length)
                negative, neg_mask = self._encode(negative_prompt, max_sequence_length) if guidance != 1 else (None, None)
                if self.cpu_offload:
                    self.text_encoder.cpu()
                self.transformer.to(self.device)
                dtype = next(self.transformer.parameters()).dtype
                generator = torch.Generator(device="cpu").manual_seed(int(seed))
                latents = torch.randn((1, self.transformer.latent_channels, height // 16, width // 16),
                                      generator=generator, dtype=torch.float32).to(self.device)
                for sigma, next_sigma in zip(sigmas[:-1], sigmas[1:]):
                    x = latents.to(dtype)
                    velocity = self.transformer(x, sigma * self.training_steps, positive.to(dtype), mask).float()
                    if negative is not None:
                        uncond = self.transformer(x, sigma * self.training_steps, negative.to(dtype), neg_mask, skip_layers=skip).float()
                        velocity = uncond + guidance * (velocity - uncond)
                    latents = latents + (next_sigma - sigma) * velocity
                if self.cpu_offload:
                    self.transformer.cpu()
                self.vae.to(self.device)
                image = self.vae.decode(latents.float()).float()
                pixels = ((image[0].permute(1, 2, 0).clamp(-1, 1) + 1) * 127.5).round().byte().cpu().numpy()
                return Image.fromarray(pixels)
            finally:
                if self.cpu_offload:
                    for model in (self.text_encoder, self.transformer, self.vae):
                        model.cpu()

    def close(self):
        with self.lock:
            for model in (self.text_encoder, self.transformer, self.vae):
                model.cpu()
