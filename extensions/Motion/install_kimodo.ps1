param(
    [string]$ProjectPython,
    [string]$EnvironmentPath
)
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $ProjectPython) {
    $ParentRoot = if ($env:SSUI_VENV_PATH) { $env:SSUI_VENV_PATH } else { Join-Path $RepoRoot ".venv" }
    $ProjectPython = Join-Path $ParentRoot "Scripts\python.exe"
}
$ProjectPython = (Resolve-Path -LiteralPath $ProjectPython).Path
$KimodoRoot = if ($EnvironmentPath) { [IO.Path]::GetFullPath($EnvironmentPath) } else { Join-Path $RepoRoot ".venv\kimodo" }
if ([string]::Equals($KimodoRoot.TrimEnd('\'), (Split-Path (Split-Path $ProjectPython)).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Kimodo must use a child environment distinct from the shared SSUI environment"
}
$KimodoPython = Join-Path $KimodoRoot "Scripts\python.exe"
$ParentSitePackages = & $ProjectPython -c "import sysconfig; print(sysconfig.get_path('purelib'))"
if ($LASTEXITCODE -ne 0) { throw "Cannot inspect the selected parent Python" }
$PthFile = Join-Path $KimodoRoot "Lib\site-packages\ssui_parent_venv.pth"
$KimodoCommit = "1aece8c124d73d255ceff5086d983b844c9f4e94"

if (-not (Test-Path -LiteralPath $ProjectPython)) {
    throw "Project venv is missing. Run yarn at the repository root first."
}

if (-not (Test-Path -LiteralPath $KimodoPython)) {
    & $ProjectPython -m venv $KimodoRoot
    if ($LASTEXITCODE -ne 0) { throw "Cannot create Kimodo environment" }
}

# Reuse the project's verified CUDA/ROCm PyTorch without upgrading the shared SSUI
# environment. Packages installed in the child environment take precedence.
[IO.File]::WriteAllText($PthFile, $ParentSitePackages + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

$env:SKIP_MOTION_CORRECTION_IN_SETUP = "1"
& $KimodoPython -m pip install --timeout 300 `
    --no-deps `
    "kimodo @ git+https://github.com/nv-tlabs/kimodo.git@$KimodoCommit"
if ($LASTEXITCODE -ne 0) { throw "Kimodo source installation failed" }
& $KimodoPython -m pip install --timeout 300 -r (Join-Path $PSScriptRoot "requirements-kimodo-inference.txt")
if ($LASTEXITCODE -ne 0) { throw "Kimodo inference dependency installation failed" }

& $KimodoPython -c "import kimodo, torch, transformers; print('kimodo:', kimodo.__file__); print('torch:', torch.__version__); print('transformers:', transformers.__version__); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'unavailable')"
