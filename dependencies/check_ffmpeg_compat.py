"""Verify native bundled tools through the actual SSUI video/audio entry points."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

os.environ.pop('IMAGEIO_FFMPEG_EXE', None)
from backend.native_tools import configure_native_tools
configure_native_tools()
import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
import whisper

binary = Path(imageio_ffmpeg.get_ffmpeg_exe())
assert Path(shutil.which('ffmpeg')).resolve() == binary.resolve()
for path in [binary, binary.with_name('ffprobe.exe'), *binary.parent.glob('*.dll')]:
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 60)[0]
    assert data[:2] == b'MZ' and data[offset:offset+4] == b'PE\0\0'
    assert struct.unpack_from('<H', data, offset+4)[0] == 0xaa64, path
with tempfile.TemporaryDirectory() as temporary:
    video = Path(temporary) / 'ssui.mp4'
    with imageio.get_writer(str(video), fps=4) as writer:
        for color in (32, 96, 160):
            writer.append_data(np.full((16, 16, 3), color, dtype=np.uint8))
    with imageio.get_reader(str(video), format='ffmpeg') as reader:
        frames = [frame for frame in reader]
        assert len(frames) == 3 and frames[0].shape == (16, 16, 3)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions/Motion'))
    from ssui import Video
    from ssui_motion.pose import _read_frames
    decoded = list(_read_frames(Video(path=str(video))))
    assert len(decoded) == 3 and all(frame.size == (16, 16) and abs(fps-4) < .01 for _, frame, fps in decoded)
    wav = Path(temporary) / 'ssui.wav'
    with wave.open(str(wav), 'wb') as dest:
        dest.setnchannels(1); dest.setsampwidth(2); dest.setframerate(16000)
        dest.writeframes(b'\0\0' * 1600)
    assert whisper.load_audio(str(wav)).shape == (1600,)
    subprocess.run([str(binary.with_name('ffprobe.exe')), '-v', 'error', str(video)], check=True)
print('Native FFmpeg: imageio H.264 round trip, Motion video input, Whisper file decoding and ffprobe passed')
