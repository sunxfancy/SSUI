"""Render MotionClip manifests to a small GIF and contact sheet with Pillow."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    points = np.asarray(manifest['positions'])
    parents = manifest['parents']
    root = parents.index(-1)
    # Root-following view: preserve vertical position while following X/Z motion.
    points[:, :, [0, 2]] -= points[:, root:root + 1, [0, 2]]
    yaw, elevation = np.deg2rad(35), np.deg2rad(8)
    right = np.array([np.cos(yaw), 0, -np.sin(yaw)])
    up = np.array([-np.sin(elevation) * np.sin(yaw), np.cos(elevation), -np.sin(elevation) * np.cos(yaw)])
    projected = np.stack([points @ right, -(points @ up)], axis=-1)
    low, high = projected.min(axis=(0, 1)), projected.max(axis=(0, 1))
    scale = 235 / max(high - low)
    center = (low + high) / 2
    pixels = (projected - center) * scale + np.array([160, 175])
    frames = []
    for frame, pose in enumerate(pixels):
        image = Image.new('RGB', (320, 320), '#101827')
        draw = ImageDraw.Draw(image)
        draw.text((12, 10), manifest['metadata']['model'], fill='#ffffff')
        draw.text((12, 28), f'{frame / manifest["fps"]:.2f}s / {len(points) / manifest["fps"]:.1f}s | root following', fill='#a7b4c8')
        for index, parent in enumerate(parents):
            if parent >= 0:
                draw.line([tuple(pose[index]), tuple(pose[parent])], fill='#5eead4', width=3)
        for x, y in pose:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill='#d5fff5')
        frames.append(image)
    folder = args.manifest.parent
    frames[0].save(folder / 'preview.gif', save_all=True, append_images=frames[1:],
                   duration=round(1000 / manifest['fps']), loop=0)
    sheet = Image.new('RGB', (320 * 4, 320))
    for column, index in enumerate(np.linspace(0, len(frames) - 1, 4, dtype=int)):
        sheet.paste(frames[index], (column * 320, 0))
    sheet.save(folder / 'contact-sheet.png')
    print(folder / 'preview.gif')


if __name__ == '__main__':
    main()
