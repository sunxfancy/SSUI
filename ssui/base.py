import PIL.Image
import trimesh

class Image():
    def __init__(self, image: PIL.Image.Image = None):
        self._image = image

class Mesh():
    def __init__(self, model: trimesh.Trimesh = None):
        self._model = model

class Video():
    def __init__(self, format: str, frames: list[PIL.Image.Image] = None, fps: int = 30):
        self._format = format
        self._frames = frames
        self._fps = fps

class Audio():
    def __init__(self, format: str, audio: bytes = None, fps: int = 16000):
        self._format = format
        self._audio = audio
        self._fps = fps

class Voice(Audio):
    def __init__(self, format: str, audio: bytes = None, fps: int = 16000, text: str = None):
        super().__init__(format, audio, fps)
        self._text = text


class Prompt():
    @staticmethod
    def create(text: str):
        return Prompt(text)

    def __init__(self, text: str):
        self._text = text
    
    def __str__(self):
        return self._text

    @property
    def text(self):
        return self._text


class Noise():
    def __init__(self, config):
        self.config = config
