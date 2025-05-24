import PIL.Image
import trimesh

class Image():
    def __init__(self, image: PIL.Image.Image = None):
        self._image = image

class Model3D():
    def __init__(self, model: trimesh.Trimesh = None):
        self._model = model


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
