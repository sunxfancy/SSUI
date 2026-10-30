"""Stable Audio Open 1.0 short sound and music sample inference."""

from pathlib import Path


MODEL_ID = "stabilityai/stable-audio-open-1.0"
MAX_SECONDS = 47.0


def _device(torch):
    # ROCm PyTorch exposes the CUDA API, including on Windows.
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class StableAudioOpenModel:
    """Thin wrapper over the official Diffusers StableAudioPipeline.

    The model is gated on Hugging Face. Callers may pass a downloaded local
    Diffusers directory to avoid authentication or network access at inference.
    """

    def __init__(self, pipeline, device: str):
        self.pipeline = pipeline
        self.device = device

    @classmethod
    def load(
        cls,
        model_path: str = MODEL_ID,
        cpu_offload: bool = True,
        dtype: str = "float16",
    ) -> "StableAudioOpenModel":
        import torch

        try:
            from diffusers import StableAudioPipeline
        except ImportError as exc:
            raise RuntimeError("Stable Audio Open requires a Diffusers build with StableAudioPipeline") from exc

        device = _device(torch)
        if dtype not in ("float16", "bfloat16", "float32"):
            raise ValueError(f"Unsupported Stable Audio dtype: {dtype}")
        torch_dtype = getattr(torch, dtype) if device != "cpu" else torch.float32
        pipeline = StableAudioPipeline.from_pretrained(model_path, torch_dtype=torch_dtype)
        if torch.version.hip is not None:
            # The default SDE scheduler can recurse in torchsde on Windows
            # ROCm; Euler sampling completed the model smoke successfully.
            from diffusers import EulerDiscreteScheduler
            pipeline.scheduler = EulerDiscreteScheduler.from_config(pipeline.scheduler.config)
        if cpu_offload and device == "cuda":
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to(device)
        return cls(pipeline, device)

    def generate(
        self,
        prompt: str,
        output_path: str | Path,
        seconds: float = 10.0,
        negative_prompt: str = "low quality, average quality",
        steps: int = 100,
        seed: int = 0,
    ) -> str:
        import soundfile as sf
        import torch

        if not prompt.strip():
            raise ValueError("Stable Audio prompt cannot be empty")
        if not 0 < seconds <= MAX_SECONDS:
            raise ValueError(f"Stable Audio duration must be within (0, {MAX_SECONDS}] seconds")
        if not 1 <= steps <= 500:
            raise ValueError("Stable Audio steps must be between 1 and 500")

        generator = torch.Generator(device=self.device).manual_seed(int(seed))
        old_miopen = torch.backends.cudnn.enabled
        try:
            if torch.version.hip is not None:
                # MIOpen VAE convolution solver search stalls on this ROCm
                # build; native PyTorch convolutions produced valid output.
                torch.backends.cudnn.enabled = False
            with torch.inference_mode():
                audio = self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=steps,
                    audio_end_in_s=float(seconds),
                    generator=generator,
                ).audios[0]
        finally:
            torch.backends.cudnn.enabled = old_miopen

        # Diffusers returns [channels, samples]; soundfile expects [samples, channels].
        waveform = audio.T.float().cpu().numpy()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), waveform, self.pipeline.vae.sampling_rate)
        return str(path)
