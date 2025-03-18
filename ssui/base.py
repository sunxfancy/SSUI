import PIL.Image
from dataclasses import dataclass

class Image():
    def __init__(self, image: PIL.Image.Image = None):
        self._image = image


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
