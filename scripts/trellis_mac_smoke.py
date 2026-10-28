"""Repository command for the portable TRELLIS runner."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions/3D-Model'))
from ssui_3dmodel.trellis_mps_runner import main
if __name__ == '__main__':
    main()
