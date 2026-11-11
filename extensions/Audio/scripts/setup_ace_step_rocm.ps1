param(
    [switch]$DownloadModel,
    [switch]$SharedPackages
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$source = Join-Path $repositoryRoot '.build\ace-step-1.5'
$vectorSource = Join-Path $repositoryRoot '.build\vector-quantize-pytorch'
$overlay = Join-Path $source '.deps'
$temporary = Join-Path $source '.tmp'

if (-not (Test-Path -LiteralPath (Join-Path $source 'acestep\handler.py'))) {
    New-Item -ItemType Directory -Force (Split-Path $source) | Out-Null
    git -c http.sslBackend=openssl clone --depth 1 https://github.com/ace-step/ACE-Step-1.5.git $source
    if ($LASTEXITCODE -ne 0) { throw 'ACE-Step source checkout failed.' }
}

if (-not (Test-Path -LiteralPath (Join-Path $vectorSource 'vector_quantize_pytorch\__init__.py'))) {
    git -c http.sslBackend=openssl clone --depth 1 https://github.com/lucidrains/vector-quantize-pytorch.git $vectorSource
    if ($LASTEXITCODE -ne 0) { throw 'vector-quantize-pytorch source checkout failed.' }
}
$vectorRevision = '9e5d4ecfdfd72abe9a4baa056d0be21532be4b69'
if ((git -C $vectorSource rev-parse HEAD) -ne $vectorRevision) {
    git -C $vectorSource -c http.sslBackend=openssl fetch --depth 1 origin $vectorRevision
    if ($LASTEXITCODE -ne 0) { throw 'Pinned vector-quantize-pytorch revision unavailable.' }
    git -C $vectorSource checkout --detach $vectorRevision
    if ($LASTEXITCODE -ne 0) { throw 'Could not select pinned vector-quantize-pytorch revision.' }
}
$vectorPatch = Join-Path $PSScriptRoot 'vector_quantize_pytorch_windows_rocm.patch'
git -C $vectorSource apply --reverse --check $vectorPatch 2>$null
if ($LASTEXITCODE -ne 0) {
    git -C $vectorSource apply --check $vectorPatch
    if ($LASTEXITCODE -ne 0) { throw 'Windows ROCm vector-quantize-pytorch source patch is incompatible.' }
    git -C $vectorSource apply $vectorPatch
    if ($LASTEXITCODE -ne 0) { throw 'Windows ROCm vector-quantize-pytorch source patch failed.' }
}

New-Item -ItemType Directory -Force $overlay, $temporary | Out-Null
$env:TEMP = $temporary
$env:TMP = $temporary
Push-Location $repositoryRoot
try {
    # The shared SSUI environment already owns the Windows ROCm PyTorch wheel.
    # Install only the upstream packages needed for inference in a local overlay.
    if (-not $SharedPackages -and -not (Test-Path -LiteralPath (Join-Path $overlay 'loguru\__init__.py'))) {
        node dependencies/venv.cjs python -m pip install --target $overlay --no-deps `
            loguru xxhash win32_setctime einx frozendict torch-einops-utils
        if ($LASTEXITCODE -ne 0) { throw 'ACE-Step dependency overlay installation failed.' }
    }

    $env:PYTHONPATH = if ($SharedPackages) { "$vectorSource;$source" } else { "$vectorSource;$overlay;$source" }
    $env:SSUI_ACE_STEP_SOURCE = $source
    if (-not $SharedPackages) { $env:SSUI_ACE_STEP_DEPS = $overlay }
    $env:SSUI_ACE_STEP_VECTOR_SOURCE = $vectorSource
    $env:SSUI_ACE_STEP_ROOT = $source
    $env:ACESTEP_CHECKPOINTS_DIR = Join-Path $source 'checkpoints'
    $env:HF_HOME = Join-Path $source '.hf'

    node dependencies/venv.cjs python -c 'import torch; from acestep.handler import AceStepHandler; print(torch.__version__, torch.version.hip, torch.cuda.is_available())'
    if ($LASTEXITCODE -ne 0) { throw 'ACE-Step import or ROCm verification failed.' }
    if ($DownloadModel) {
        node dependencies/venv.cjs python -m acestep.model_downloader --model main --dir $env:ACESTEP_CHECKPOINTS_DIR
        if ($LASTEXITCODE -ne 0) { throw 'ACE-Step model download failed.' }
    }
} finally {
    Pop-Location
}

Write-Host "ACE-Step source: $source"
Write-Host "Set SSUI_ACE_STEP_ROOT=$source before running workflow-audio.py."
