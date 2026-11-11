param(
    [Parameter(Mandatory = $true)][string]$RuntimeVenv,
    [Parameter(Mandatory = $true)][string]$DevelInclude,
    [string]$SourceRoot = '.build/holopart',
    [string]$GfxArch = 'gfx1201'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = (Resolve-Path $SourceRoot).Path
$runtime = (Resolve-Path $RuntimeVenv).Path
$headers = (Resolve-Path $DevelInclude).Path
$environment = Join-Path $source 'env'
$python = Join-Path $environment 'Scripts/python.exe'
$core = Join-Path $runtime 'Lib/site-packages/_rocm_sdk_core'
if (-not (Test-Path (Join-Path $core 'bin/hipcc.exe'))) { throw 'Matching native Windows ROCm SDK required' }
if (-not (Test-Path (Join-Path $headers 'thrust/complex.h'))) { throw 'ROCm development headers required' }
if (-not (Test-Path $python)) {
    & (Join-Path $runtime 'Scripts/python.exe') -m venv --system-site-packages $environment
    if ($LASTEXITCODE) { throw 'Could not create isolated HoloPart environment' }
}
Set-Content (Join-Path $environment 'Lib/site-packages/ssui-shared-rocm.pth') (Join-Path $runtime 'Lib/site-packages')
$env:ROCM_HOME = $core
$env:ROCM_PATH = $core
$env:HIP_PATH = $core
$env:ROCM_DEVEL_INCLUDE = $headers
$env:GPU_ARCHS = $GfxArch
$env:PYTORCH_ROCM_ARCH = $GfxArch
$env:FORCE_ONLY_CUDA = '1'
$env:FORCE_CUDA = '1'
$env:MAX_JOBS = '4'
$env:PATH = "$(Join-Path $core 'bin');$env:PATH"
& $python (Join-Path $repo 'scripts/prepare_holopart_rocm.py') $source
if ($LASTEXITCODE) { throw 'Could not prepare HIP sources' }
$wheels = Join-Path $source 'wheels'
foreach ($package in @('pytorch_cluster', 'diso')) {
    & $python -m pip wheel (Join-Path $source $package) --wheel-dir $wheels --no-build-isolation --no-deps
    if ($LASTEXITCODE) { throw "HIP build failed: $package" }
}
foreach ($wheel in (Get-ChildItem $wheels -Filter '*+rocm72-*.whl')) {
    & $python -m pip install --no-deps --force-reinstall $wheel.FullName
    if ($LASTEXITCODE) { throw "Install failed: $($wheel.Name)" }
}
& $python -m pip install pymeshlab jaxtyping typeguard
if ($LASTEXITCODE) { throw 'HoloPart Python dependencies failed' }
Push-Location $repo
try {
    & $python tests/holopart_rocm_kernel_check.py
    if ($LASTEXITCODE) { throw 'HIP numerical validation failed' }
} finally { Pop-Location }
