# Prepare HeartMuLa inference on Windows ROCm, reusing shared Audio packages
# when available. Torchtune remains isolated because its imports need a shim.
param(
    [switch]$DownloadModel
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$modelsRoot = Join-Path $repositoryRoot '.build\audio-models'
$source = Join-Path $modelsRoot 'heartlib'
$site = Join-Path $modelsRoot 'heart-rocm-site'
$temporary = Join-Path $modelsRoot 'tmp'
$shim = Join-Path $repositoryRoot 'extensions\Audio\ssui_audio\heart_rocm_shim'
$vector = Join-Path $repositoryRoot '.build\vector-quantize-pytorch'
$aceDependencies = Join-Path $repositoryRoot '.build\ace-step-1.5\.deps'

New-Item -ItemType Directory -Force $modelsRoot, $temporary | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $source 'examples\run_music_generation.py'))) {
    git -c http.sslBackend=openssl clone --depth 1 https://github.com/HeartMuLa/heartlib.git $source
    if ($LASTEXITCODE -ne 0) { throw 'HeartMuLa source checkout failed.' }
}

node (Join-Path $repositoryRoot 'dependencies\venv.cjs') python -c 'import vector_quantize_pytorch, loguru, xxhash, einx'
$sharedReady = $LASTEXITCODE -eq 0
if ($sharedReady) {
    & (Join-Path $PSScriptRoot 'setup_ace_step_rocm.ps1') -SharedPackages
} else {
    & (Join-Path $PSScriptRoot 'setup_ace_step_rocm.ps1')
}

$env:TEMP = $temporary
$env:TMP = $temporary
Push-Location $repositoryRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $site 'torchtune\__init__.py'))) {
        node dependencies/venv.cjs python -m pip install --target $site --no-deps torchtune==0.4.0
        if ($LASTEXITCODE -ne 0) { throw 'Torchtune inference overlay installation failed.' }
    }
    $env:SSUI_HEARTMULA_DEPS = $site
    $env:SSUI_HEARTMULA_SOURCE = $source
    $env:PYTHONPATH = if ($sharedReady) {
        "$shim;$site;$(Join-Path $source 'src')"
    } else {
        "$shim;$vector;$aceDependencies;$site;$(Join-Path $source 'src')"
    }
    node dependencies/venv.cjs python (Join-Path $source 'examples\run_music_generation.py') --help
    if ($LASTEXITCODE -ne 0) { throw 'HeartMuLa inference CLI import failed.' }
    if ($DownloadModel) {
        $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
        $env:HF_HOME = Join-Path $modelsRoot 'hf'
        node dependencies/venv.cjs python (Join-Path $PSScriptRoot 'download_heartmula.py') `
            --output (Join-Path $modelsRoot 'heart-checkpoints')
        if ($LASTEXITCODE -ne 0) { throw 'HeartMuLa model download failed.' }
    }
} finally {
    Pop-Location
}

Write-Host "HeartMuLa source: $source"
Write-Host "HeartMuLa dependency site: $site"
Write-Host "HeartMuLa checkpoints: $(Join-Path $modelsRoot 'heart-checkpoints')"
Write-Host 'Set SSUI_HEARTMULA_CHECKPOINT to the official multi-component checkpoint directory before generation.'
