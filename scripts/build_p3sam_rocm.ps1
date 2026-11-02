param(
    [Parameter(Mandatory = $true)][string]$RuntimeVenv,
    [Parameter(Mandatory = $true)][string]$DevelInclude,
    [string]$SourceRoot = '.build/retopology',
    [string]$GfxArch = 'gfx1201'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = (Resolve-Path $RuntimeVenv).Path
$source = (Resolve-Path $SourceRoot).Path
$headers = (Resolve-Path $DevelInclude).Path
$environment = Join-Path $source 'p3sam-rocm-env'
$python = Join-Path $environment 'Scripts/python.exe'
$core = Join-Path $runtime 'Lib/site-packages/_rocm_sdk_core'
if (-not (Test-Path (Join-Path $core 'bin/hipcc.exe'))) { throw 'Matching Windows ROCm SDK is required' }
if (-not (Test-Path (Join-Path $headers 'thrust/complex.h'))) { throw 'Extracted ROCm development headers are required' }
if (-not (Test-Path $python)) {
    & (Join-Path $runtime 'Scripts/python.exe') -m venv --system-site-packages $environment
    if ($LASTEXITCODE) { throw 'Could not create isolated build environment' }
}
# The runtime venv uses a bundled base Python; its packages need an explicit path.
Set-Content (Join-Path $environment 'Lib/site-packages/ssui-shared-rocm.pth') (Join-Path $runtime 'Lib/site-packages')
$env:ROCM_HOME = $core
$env:ROCM_PATH = $core
$env:HIP_PATH = $core
$env:ROCM_DEVEL_INCLUDE = $headers
$env:BUILD_TARGET = 'rocm'
$env:GPU_ARCHS = $GfxArch
$env:PYTORCH_ROCM_ARCH = $GfxArch
$env:MAX_JOBS = '4'
$env:FLEX_GEMM_CACHE_DIR = Join-Path $source 'flex-cache'
$env:PATH = "$(Join-Path $core 'bin');$env:PATH"
$wheels = Join-Path $source 'wheels'
New-Item -ItemType Directory -Force $wheels | Out-Null
& $python (Join-Path $repo 'scripts/prepare_scatter_rocm.py') (Join-Path $source 'pytorch_scatter')
if ($LASTEXITCODE) { throw 'Could not prepare torch-scatter source' }
foreach ($package in @('FlexGEMM', 'pytorch_scatter')) {
    if ($package -eq 'pytorch_scatter') { $env:FORCE_ONLY_CUDA = '1' }
    & $python -m pip wheel (Join-Path $source $package) --wheel-dir $wheels --no-build-isolation --no-deps --no-cache-dir
    if ($LASTEXITCODE) { throw "ROCm build failed: $package" }
}
$builtWheels = Get-ChildItem $wheels -Filter '*+rocm72-cp312-cp312-win_amd64.whl'
foreach ($wheel in $builtWheels) {
    & $python -m pip install --no-deps --force-reinstall $wheel.FullName
    if ($LASTEXITCODE) { throw "Wheel installation failed: $($wheel.Name)" }
}
& $python -m pip install --no-deps fpsample addict
if ($LASTEXITCODE) { throw 'Sampling dependencies could not be installed' }
& $python (Join-Path $repo 'tests/p3sam_rocm_kernel_check.py')
if ($LASTEXITCODE) { throw 'ROCm kernel numerical checks failed' }
