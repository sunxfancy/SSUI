"""Run real CosyVoice2 inference from the repository's shared environment."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'extensions/Voice'), str(ROOT / 'extensions/Voice/vendor')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', help='Local CosyVoice2 snapshot; otherwise download into models/CosyVoice2-0.5B')
    parser.add_argument('--prompt', required=True, help='Reference WAV, at most 30 seconds')
    parser.add_argument('--prompt-text', required=True, help='Exact reference transcript')
    parser.add_argument('--text', default='你好，这是使用 CosyVoice 二进行的语音合成测试。')
    parser.add_argument('--text-frontend', action='store_true', help='Enable text normalization (first FST build can use substantial RAM)')
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--output', default='artifacts/cosyvoice2/output.wav')
    args = parser.parse_args()
    if args.device == 'cpu':
        import os
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    import soundfile as sf
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but PyTorch cannot access an NVIDIA GPU')
    from ssui_voice.Cosyvoice import CosyVoiceModel, GenVoice
    from ssui.base import Audio
    from ssui.config import SSUIConfig
    if not args.model:
        from huggingface_hub import snapshot_download
        args.model = snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir=ROOT / 'models/CosyVoice2-0.5B',
                                       ignore_patterns=['*.zip', '*.plan', '*.engine', '*.trt', 'llm.onnx', 'flow.decoder*.onnx'])
    torch.set_num_threads(4)
    model = CosyVoiceModel.load(args.model)
    devices = {name: str(next(getattr(model.model.model, name).parameters()).device)
               for name in ('llm', 'flow', 'hift')}
    if args.device == 'cuda' and any(not value.startswith('cuda') for value in devices.values()):
        raise RuntimeError(f'Models did not load on CUDA: {devices}')
    if args.device == 'cuda' and 'CUDAExecutionProvider' not in model.model.frontend.speech_tokenizer_session.get_providers():
        raise RuntimeError('CUDA was requested but ONNX Runtime did not activate CUDAExecutionProvider')
    config = SSUIConfig()
    config('speech')
    config._is_prepare = True
    GenVoice(config, model, args.text)
    config._is_prepare = False
    started = time.perf_counter()
    result = GenVoice(config, model, args.text, Audio('wav', Path(args.prompt).read_bytes()), args.prompt_text, text_frontend=args.text_frontend)
    inference_seconds = time.perf_counter() - started
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result._audio)
    audio, rate = sf.read(output)
    import numpy as np
    if audio.size == 0 or not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-5:
        raise RuntimeError('Generated audio is empty, invalid, or silent')
    report = {'model': str(args.model), 'torch': torch.__version__, 'device': str(model.model.model.device),
              'gpu_name': torch.cuda.get_device_name(0) if model.model.model.device.type == 'cuda' else None,
              'inference_seconds': inference_seconds, 'model_devices': devices, 'onnx_providers': model.model.frontend.speech_tokenizer_session.get_providers(),
              'sample_rate': rate, 'duration_seconds': len(audio) / rate,
              'peak': float(np.max(np.abs(audio))), 'rms': float(np.sqrt(np.mean(audio**2))),
              'output': str(output)}
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
