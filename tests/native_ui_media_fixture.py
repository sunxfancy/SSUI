"""Installed only into an isolated desktop test SDK; no ML inference is claimed."""
from PIL import Image
import trimesh
from ssui.base import Video, Mesh


def make_assets():
    frames = [Image.new('RGB', (32, 32), (index * 12, 60, 200 - index * 8)) for index in range(16)]
    return Video('mp4', frames, fps=8), Mesh(trimesh.creation.box())
