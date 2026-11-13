"""Real CosyVoice2 inference through SSUI; run with yarn probe:cosyvoice."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path[:0] = [str(ROOT / "extensions/Voice"), str(ROOT / "extensions/Voice/vendor")]

MODEL_REPO = "FunAudioLLM/CosyVoice2-0.5B"
MODEL_REVISION = "eec1ae6c79877dbd9379285cf8789c9e0879293d"
PROMPT_URL = "https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/main/asset/zero_shot_prompt.wav"
PROMPT_SHA256 = "c7b31d6dbe7cc6a716dded00550db5b50940bf209e424e4ad207b12e657c8ff6"
PROMPT_TEXT = "希望你以后能够做的比我还好呦。"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / ".build/models/CosyVoice2-0.5B")
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--prompt-text", default=PROMPT_TEXT)
    parser.add_argument("--text", default="你好，这是使用 AMD 显卡生成的语音。欢迎使用语音合成。")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".build/cosyvoice")
    parser.add_argument("--download", action="store_true", help="Download the pinned official model and example prompt")
    parser.add_argument("--require-rocm", action="store_true")
    parser.add_argument("--cross-lingual", action="store_true")
    parser.add_argument("--threads", type=int, default=4, help="CPU threads for preprocessing (default: 4)")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / ".build/numba-cache"))
    os.environ.setdefault("SSUI_COSYVOICE_TN_CACHE", str(ROOT / ".build/cosyvoice-tn"))
    for name, folder in (("MIOPEN_USER_DB_PATH", "miopen-db"),
                         ("MIOPEN_CUSTOM_CACHE_DIR", "miopen-cache")):
        cache = Path(os.environ.setdefault(name, str(ROOT / ".build" / folder)))
        cache.mkdir(parents=True, exist_ok=True)

    import soundfile as sf
    import torch
    from ssui.base import Audio
    from ssui.config import SSUIConfig
    from ssui_voice.Cosyvoice import CosyVoiceModel, GenVoice

    if args.threads < 1:
        raise ValueError("--threads must be positive")
    torch.set_num_threads(args.threads)
    if args.require_rocm and not (torch.version.hip and torch.cuda.is_available()):
        raise RuntimeError("A working ROCm PyTorch GPU is required")
    prompt = args.prompt or args.output_dir / "prompt.wav"
    if args.download:
        from huggingface_hub import snapshot_download
        snapshot_download(MODEL_REPO, revision=MODEL_REVISION, local_dir=args.model_dir,
                          allow_patterns=["CosyVoice-BlankEN/*", "cosyvoice2.yaml", "campplus.onnx",
                                          "speech_tokenizer_v2.onnx", "llm.pt", "flow.pt", "hift.pt"])
        if args.prompt is None and not prompt.exists():
            urllib.request.urlretrieve(PROMPT_URL, prompt)
        if args.prompt is None and hashlib.sha256(prompt.read_bytes()).hexdigest() != PROMPT_SHA256:
            raise RuntimeError("Official reference audio checksum mismatch; supply your own --prompt and --prompt-text")
    if not prompt.is_file():
        raise FileNotFoundError(f"Reference audio missing: {prompt}; supply --prompt or --download")

    start = time.perf_counter()
    model = CosyVoiceModel.load(str(args.model_dir))
    engine = model.getModel()
    components = {name: str(next(getattr(engine.model, name).parameters()).device)
                  for name in ("llm", "flow", "hift")}
    if args.require_rocm and any(not device.startswith("cuda") for device in components.values()):
        raise RuntimeError(f"Model is not on the ROCm GPU: {components}")
    load_seconds = time.perf_counter() - start
    config = SSUIConfig()("cosyvoice")
    config["use_zero_shot"] = not args.cross_lingual
    start = time.perf_counter()
    voice = GenVoice(config, model, args.text, Audio.load(str(prompt)), args.prompt_text)
    samples = voice._audio
    if not torch.isfinite(samples).all() or samples.numel() == 0 or samples.abs().max() == 0:
        raise RuntimeError("Generated audio is empty, silent, or nonfinite")
    elapsed = time.perf_counter() - start
    output = args.output_dir / ("cross_lingual.wav" if args.cross_lingual else "zero_shot.wav")
    sf.write(str(output), samples.squeeze(0).numpy(), voice.sample_rate)
    report = {
        "torch": torch.__version__, "hip": torch.version.hip,
        "gpu": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        "components": components, "onnx_providers": engine.frontend.speech_tokenizer_session.get_providers(),
        "model_revision": MODEL_REVISION, "model_dir": str(args.model_dir.resolve()),
        "sample_rate": voice.sample_rate, "audio_seconds": samples.shape[-1] / voice.sample_rate,
        "load_seconds": load_seconds, "inference_seconds": elapsed,
        "peak": samples.abs().max().item(), "rms": samples.square().mean().sqrt().item(),
        "output": str(output.resolve()), "text": args.text,
    }
    report_path = output.with_suffix(".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
