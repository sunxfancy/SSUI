param([switch]$DownloadModel)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$modelRoot = Join-Path $repositoryRoot '.build\audio-models'
$source = Join-Path $modelRoot 'yue'
$weights = Join-Path $modelRoot 'yue-weights'
$vae = Join-Path $modelRoot 'yue-vae'
New-Item -ItemType Directory -Force $modelRoot | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $source 'src\yue2'))) {
    git -c http.sslBackend=openssl clone --depth 1 https://github.com/satecay/yue.git $source
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 source checkout failed.' }
}

$env:HF_HOME = Join-Path $modelRoot 'hf'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:TEMP = Join-Path $modelRoot 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

Push-Location $repositoryRoot
try {
    node dependencies/venv.cjs python -c "import torch,sys; sys.path.insert(0, r'$source\src'); from yue2 import YuE2Pipeline; print(torch.__version__, torch.version.hip, torch.cuda.is_available())"
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 import or ROCm verification failed.' }
    if ($DownloadModel) {
        node dependencies/venv.cjs python -c "from huggingface_hub import snapshot_download; snapshot_download('m-a-p/YuE2-3B', local_dir=r'$weights'); snapshot_download('m-a-p/YuE2-Vae', local_dir=r'$vae')"
        if ($LASTEXITCODE -ne 0) { throw 'YuE2 weight download failed.' }
    }
} finally {
    Pop-Location
}

Write-Host "YuE2 source: $source"
Write-Host "YuE2 weights: $weights"
Write-Host "YuE2 VAE: $vae"
