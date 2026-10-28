param(
    [string]$Source = ".build/nvdiffrast-repro/source",
    [string]$VenvRoot = ".venv",
    [string]$GfxArch = "gfx1201",
    [string]$DevelInclude = ".build/nvdiffrast-repro/headers"
)
$ErrorActionPreference = "Stop"
if ($GfxArch -ne "gfx1201") { throw "This kernel patch set is validated only for gfx1201." }
$venv = (Resolve-Path $VenvRoot).Path
$sourcePath = (Resolve-Path $Source).Path
$core = Join-Path $venv "Lib/site-packages/_rocm_sdk_core"
$env:ROCM_HOME = $core
$env:ROCM_PATH = $core
$env:HIP_PATH = $core
$env:ROCM_DEVEL_INCLUDE = (Resolve-Path $DevelInclude).Path
$env:GPU_ARCHS = $GfxArch
$env:PYTORCH_ROCM_ARCH = $GfxArch
$env:MAX_JOBS = "4"
$env:PATH = "$(Join-Path $core 'bin');$env:PATH"
$env:PYTHONUTF8 = "1"
& (Join-Path $venv "Scripts/python.exe") -m pip wheel $sourcePath --wheel-dir (Join-Path $sourcePath "dist") --no-build-isolation --no-deps --no-cache-dir
if ($LASTEXITCODE -ne 0) { throw "ROCm extension build failed ($LASTEXITCODE): $sourcePath" }
