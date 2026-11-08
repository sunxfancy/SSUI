"""Audio file I/O independent of TorchAudio's optional TorchCodec backend."""
import numpy as np


def write_audio(path, audio, sample_rate):
    import soundfile
    if hasattr(audio, "detach"):
        audio = audio.detach().float().cpu().numpy()
    samples = np.asarray(audio)
    if samples.ndim == 2:
        samples = samples.T  # SSUI tensors use channels, samples.
    soundfile.write(path, samples, sample_rate)
