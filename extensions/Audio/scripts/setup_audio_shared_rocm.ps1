# Install compatible Audio inference packages into the Python environment used
# by this SSUI checkout. Keep model-specific conflicts in isolated overlays.
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$modelsRoot = Join-Path $repositoryRoot '.build\audio-models'
$wheelRoot = Join-Path $repositoryRoot '.build\audio-wheels'
New-Item -ItemType Directory -Force $modelsRoot, $wheelRoot | Out-Null
$env:UV_CACHE_DIR = Join-Path $modelsRoot 'uv-cache'
$env:TEMP = Join-Path $modelsRoot 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

Push-Location $repositoryRoot
try {
    $python = (node dependencies/venv.cjs python -c 'import sys; print(sys.executable)' | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $python) { throw 'Could not resolve SSUI Python.' }
    $before = (node dependencies/venv.cjs python -c 'import torch,transformers; print(torch.__version__, transformers.__version__)' | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $before) { throw 'ROCm torch or Transformers is unavailable.' }

    node dependencies/venv.cjs python -m uv pip install --no-deps --python $python `
        -r (Join-Path $PSScriptRoot 'shared_rocm_requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Shared Audio package installation failed.' }

    & (Join-Path $PSScriptRoot 'setup_ace_step_rocm.ps1') -SharedPackages
    if ($LASTEXITCODE -ne 0) { throw 'ACE-Step source preparation failed.' }
    $vectorSource = Join-Path $repositoryRoot '.build\vector-quantize-pytorch'
    node dependencies/venv.cjs python -m uv build $vectorSource --out-dir $wheelRoot
    if ($LASTEXITCODE -ne 0) { throw 'ROCm-compatible vector quantizer wheel build failed.' }
    $wheel = Join-Path $wheelRoot 'vector_quantize_pytorch-1.32.0-py3-none-any.whl'
    if (-not (Test-Path -LiteralPath $wheel)) { throw 'Vector quantizer wheel was not produced.' }
    node dependencies/venv.cjs python -m uv pip install --no-deps --python $python $wheel
    if ($LASTEXITCODE -ne 0) { throw 'Shared vector quantizer install failed.' }

    $after = (node dependencies/venv.cjs python -c 'import torch,transformers; print(torch.__version__, transformers.__version__)' | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or $after -ne $before) { throw "Core versions changed: $before -> $after" }
    node dependencies/venv.cjs python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Shared Python dependency check failed.' }
} finally {
    Pop-Location
}

Write-Host "Shared Audio packages installed in $python"
Write-Host "ROCm torch and Transformers preserved: $after"
