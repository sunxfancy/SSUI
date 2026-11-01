"""Persist typed workflow outputs before reporting successful task completion."""
from pathlib import Path
import uuid
import shutil
import numpy as np
from ssui.base import Image, Mesh, Video


def serialize_result(result, project_root):
    if isinstance(result, (tuple, list)):
        return [serialize_result(value, project_root) for value in result]
    if result is None:
        return None
    if not isinstance(result, (Image, Video, Mesh)):
        raise TypeError(f'Unsupported workflow output: {type(result).__name__}')
    if not project_root:
        raise ValueError('Workflow output requires an ssproject.yaml project root')
    output = Path(project_root) / 'output'
    output.mkdir(parents=True, exist_ok=True)
    kind, suffix = ('image', 'png') if isinstance(result, Image) else (
        ('video', 'mp4') if isinstance(result, Video) else ('3dmodel', 'glb'))
    path = output / f'{kind}_{uuid.uuid4().hex}.{suffix}'
    created = [path]
    artifacts = []
    try:
        if isinstance(result, Image):
            result._image.save(path)
        elif isinstance(result, Mesh):
            result._model.export(path)
        else:
            if result._format != 'mp4':
                raise ValueError('Video output currently supports mp4')
            if not result._frames or result._fps <= 0:
                raise ValueError('Video output requires frames and a positive FPS')
            import imageio.v2 as iio
            with iio.get_writer(str(path), fps=result._fps, codec='libx264',
                                pixelformat='yuv420p', macro_block_size=1) as writer:
                for frame in result._frames:
                    frame = frame._image if isinstance(frame, Image) else frame
                    writer.append_data(np.asarray(frame.convert('RGB')))
        if isinstance(result, Video):
            for name, source in result._artifacts.items():
                source = Path(source)
                target = output / f'artifact_{uuid.uuid4().hex}{source.suffix}'
                created.append(target)
                shutil.copyfile(source, target)
                artifacts.append({'name': name, 'path': str(target)})
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError('Workflow output file is empty')
    except Exception:
        for item in created:
            item.unlink(missing_ok=True)
        raise
    payload = {'type': kind, 'path': str(path)}
    if artifacts:
        payload['artifacts'] = artifacts
    return payload
