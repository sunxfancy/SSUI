$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ProjectPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$KimodoPython = $ProjectPython
$KimodoCommit = "1aece8c124d73d255ceff5086d983b844c9f4e94"

if (-not (Test-Path -LiteralPath $ProjectPython)) {
    throw "Project venv is missing. Run yarn at the repository root first."
}

# The shared backend now uses Transformers 5.1.0. Do not create a child venv
# or leak the parent site-packages into it through .pth files.

$env:SKIP_MOTION_CORRECTION_IN_SETUP = "1"
& $KimodoPython -m pip install --timeout 300 `
    "kimodo @ git+https://github.com/nv-tlabs/kimodo.git@$KimodoCommit"

& $KimodoPython -c "import kimodo, torch, transformers; print('kimodo:', kimodo.__file__); print('torch:', torch.__version__); print('transformers:', transformers.__version__); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'unavailable')"
