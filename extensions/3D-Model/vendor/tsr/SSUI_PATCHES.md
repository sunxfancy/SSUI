Upstream: https://github.com/VAST-AI-Research/TripoSR
Commit: 107cefdc244c39106fa830359024f6a2f1c78871
License: MIT (see LICENSE). tests/fixtures/3d/chair.png is from upstream examples/chair.png.

SSUI changes: CPU scikit-image marching cubes replaces torchmcubes (array-axis coordinates are preserved); local DINO configuration loading supports offline use; rembg is imported only when background removal is requested. The SSUI node accepts transparent inputs or preprocessed RGB and exports vertex colors without CUDA texture baking.

DINO position-table bicubic interpolation runs on CPU for Torch 2.4 MPS; foreground cropping includes the final occupied pixel.
