"""HeartMuLa inference with a soundfile/FFmpeg output path for Windows ROCm.

The Windows ROCm torchaudio wheel lacks TorchCodec, which upstream uses to save
MP3. This runner keeps upstream model inference and replaces only that output
step. It is launched in the isolated HeartMuLa subprocess environment.
"""

import argparse
import os
import subprocess
import tempfile

import imageio_ffmpeg
import soundfile as sf
import torch

from heartlib import HeartMuLaGenPipeline


class RocmHeartPipeline(HeartMuLaGenPipeline):
    def _apply_compile(self, model):
        # Upstream torch.compile uses Inductor/Triton, whose ROCm compiler is
        # unavailable in the Windows wheel. Eager inference remains supported.
        return None

    def postprocess(self, model_outputs, save_path):
        frames = model_outputs["frames"].to(self.codec_device)
        waveform = self.codec.detokenize(frames)
        self._unload()
        with tempfile.TemporaryDirectory(prefix="ssui-heart-wav-") as directory:
            wav_path = os.path.join(directory, "song.wav")
            audio = waveform.to(torch.float32).cpu().numpy().T
            sf.write(wav_path, audio, 48000)
            subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                 "-i", wav_path, save_path],
                check=True,
            )


def _dtype(value):
    return {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}[value]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--version", default="3B")
    parser.add_argument("--lyrics", required=True)
    parser.add_argument("--tags", required=True)
    parser.add_argument("--save_path", required=True)
    parser.add_argument("--max_audio_length_ms", type=int, default=240000)
    parser.add_argument("--topk", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--cfg_scale", type=float, default=3.0)
    parser.add_argument("--mula_device", default="cuda")
    parser.add_argument("--codec_device", default="cuda")
    parser.add_argument("--mula_dtype", choices=("float32", "float16", "bfloat16"), default="bfloat16")
    parser.add_argument("--codec_dtype", choices=("float32", "float16", "bfloat16"), default="float32")
    parser.add_argument("--lazy_load", choices=("true", "false"), default="false")
    arguments = parser.parse_args()

    # MIOpen's Windows ROCm convolution solver can spend minutes searching for
    # codec kernels and still fail workspace selection. Use native eager ops.
    if torch.version.hip is not None:
        torch.backends.cudnn.enabled = False

    pipeline = RocmHeartPipeline.from_pretrained(
        arguments.model_path,
        device={"mula": torch.device(arguments.mula_device), "codec": torch.device(arguments.codec_device)},
        dtype={"mula": _dtype(arguments.mula_dtype), "codec": _dtype(arguments.codec_dtype)},
        version=arguments.version,
        lazy_load=arguments.lazy_load == "true",
    )
    with torch.no_grad():
        pipeline(
            {"lyrics": arguments.lyrics, "tags": arguments.tags},
            max_audio_length_ms=arguments.max_audio_length_ms,
            save_path=arguments.save_path,
            topk=arguments.topk,
            temperature=arguments.temperature,
            cfg_scale=arguments.cfg_scale,
        )


if __name__ == "__main__":
    main()
