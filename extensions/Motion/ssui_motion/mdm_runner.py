"""Run official MDM in its own interpreter with legacy asset compatibility."""
import argparse
import inspect
import os
from pathlib import Path
import runpy
import sys
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    args, remaining = parser.parse_known_args()
    root = Path(args.repo).resolve()
    if not (root / 'sample/generate.py').is_file():
        parser.error('Expected an official motion-diffusion-model checkout')
    # The official SMPL pickle uses Chumpy (Python 3.7 / NumPy < 1.24).
    # Keep these aliases confined to the isolated motion subprocess.
    if not hasattr(inspect, 'getargspec'):
        inspect.getargspec = inspect.getfullargspec
    for name, value in dict(bool=bool, int=int, float=float, complex=complex,
                            object=object, str=str, unicode=str).items():
        if name not in np.__dict__:
            setattr(np, name, value)
    # MoviePy 1.x calls the RGB canvas API removed by Matplotlib 3.10.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    if not hasattr(FigureCanvasAgg, "tostring_rgb"):
        FigureCanvasAgg.tostring_rgb = lambda canvas: np.asarray(canvas.buffer_rgba())[..., :3].tobytes()
    os.chdir(root)
    sys.path.insert(0, str(root))
    sys.argv = ['sample.generate', *remaining]
    runpy.run_module('sample.generate', run_name='__main__')


if __name__ == '__main__':
    main()
