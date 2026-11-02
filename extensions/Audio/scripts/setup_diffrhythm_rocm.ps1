param([switch]$CheckCli = $true, [switch]$SharedPackages)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$modelRoot = Join-Path $repositoryRoot '.build\audio-models'
$source = Join-Path $modelRoot 'DiffRhythm'
$overlay = Join-Path $modelRoot $(if ($SharedPackages) { 'diff-compat-site' } else { 'diff-site' })
$temporary = Join-Path $modelRoot 'tmp'
$revision = '28ad63c0f096fe2ee258bcabbcf081d5d9366afd'

New-Item -ItemType Directory -Force $modelRoot, $temporary | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $source 'infer\infer.py'))) {
    git -c http.sslBackend=openssl clone --depth 1 https://github.com/ASLP-lab/DiffRhythm.git $source
    if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm source checkout failed.' }
}
if ((git -C $source rev-parse HEAD) -ne $revision) {
    git -C $source -c http.sslBackend=openssl fetch --depth 1 origin $revision
    if ($LASTEXITCODE -ne 0) { throw 'Pinned DiffRhythm revision unavailable.' }
    git -C $source checkout --detach $revision
    if ($LASTEXITCODE -ne 0) { throw 'Could not select pinned DiffRhythm revision.' }
}

# Upstream imports its training module (and wandb) from model/__init__.py,
# even when only running infer.py. Keep this narrow, reviewable source change
# separate from the inference adapter until it can be upstreamed.
$sourcePatch = Join-Path $PSScriptRoot 'diffrhythm_inference_only.patch'
git -C $source apply --reverse --check $sourcePatch 2>$null
if ($LASTEXITCODE -ne 0) {
    git -C $source apply --check $sourcePatch
    if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm inference-only patch is incompatible.' }
    git -C $source apply $sourcePatch
    if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm inference-only patch failed.' }
}

New-Item -ItemType Directory -Force $overlay | Out-Null
$env:TEMP = $temporary
$env:TMP = $temporary
Push-Location $repositoryRoot
try {
    if ($SharedPackages) {
        node dependencies/venv.cjs python -c 'import muq, phonemizer, torchdiffeq, x_transformers, pykakasi, pandas'
        if ($LASTEXITCODE -ne 0) { throw 'Run setup_audio_shared_rocm.ps1 first.' }
        if (-not (Test-Path -LiteralPath (Join-Path $overlay 'transformers-4.49.0.dist-info'))) {
            $python = (node dependencies/venv.cjs python -c 'import sys; print(sys.executable)' | Select-Object -Last 1).Trim()
            node dependencies/venv.cjs python -m uv pip install --target $overlay --no-deps --python $python `
                transformers==4.49.0 tokenizers==0.21.1 prefigure==0.0.10
            if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm compatibility overlay installation failed.' }
        }
    } elseif (-not (Test-Path -LiteralPath (Join-Path $overlay 'muq\__init__.py'))) {
        # Fallback for machines that keep every DiffRhythm package isolated.
        node dependencies/venv.cjs python -m pip install --target $overlay --no-deps `
            muq==0.1.0 phonemizer==3.3.0 torchdiffeq==0.2.5 x-transformers==2.1.2 `
            pykakasi==2.3.0 jieba==0.42.1 cn2an==0.5.23 pypinyin==0.53.0 `
            Unidecode==1.3.8 inflect==7.5.0 py3langid==0.2.2 x-clip nnAudio easydict `
            einx beartype ftfy regex frozendict mutagen==1.47.0 loguru==0.7.3 `
            pandas==2.2.3 prefigure==0.0.10 ema-pytorch==0.7.7 win32-setctime `
            segments==2.4.0 dlinfo==2.0.0 csvw==4.1.1 isodate==0.7.2 `
            'rfc3986<2' uritemplate==4.2.0 language-tags==1.3.2 rdflib==7.6.0 `
            proces==0.1.7 typeguard==4.6.0 `
            transformers==4.49.0 tokenizers==0.21.1
        if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm dependency overlay installation failed.' }
    }
    $env:PYTHONPATH = "$overlay;$source"
    $espeakRoot = Join-Path $modelRoot 'espeak-ng\eSpeak NG'
    if (Test-Path -LiteralPath (Join-Path $espeakRoot 'libespeak-ng.dll')) {
        $env:PHONEMIZER_ESPEAK_LIBRARY = Join-Path $espeakRoot 'libespeak-ng.dll'
        $env:PHONEMIZER_ESPEAK_PATH = $espeakRoot
        $env:ESPEAK_DATA_PATH = $espeakRoot
        $env:PATH = "$espeakRoot;$env:PATH"
    }
    $env:PYTHONIOENCODING = 'utf-8'
    if ($CheckCli) {
        node dependencies/venv.cjs python (Join-Path $source 'infer\infer.py') --help
        if ($LASTEXITCODE -ne 0) { throw 'DiffRhythm CLI import failed.' }
    }
} finally {
    Pop-Location
}

Write-Host "DiffRhythm source: $source"
Write-Host "DiffRhythm overlay: $overlay"
