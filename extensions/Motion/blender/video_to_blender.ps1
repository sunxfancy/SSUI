param(
    [Parameter(Mandatory = $true)]
    [string]$Video,
    [string]$OutputDir = 'output/video-to-blender',
    [double]$SampleFps = 24.0,
    [double]$Smoothing = 0.45,
    [string]$ModelPath,
    [string]$PythonExecutable,
    [string]$BlenderExecutable,
    [switch]$SkipBlender
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$videoPath = (Resolve-Path $Video).Path
$outputPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) {
    [System.IO.Path]::GetFullPath($OutputDir)
} else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDir))
}
$motionScript = Join-Path $PSScriptRoot 'video_to_motion.py'

if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $repoRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "SSUI Python environment not found: $PythonExecutable. Run yarn first or pass -PythonExecutable."
}

$motionArgs = @(
    $motionScript,
    '--video', $videoPath,
    '--output-dir', $outputPath,
    '--sample-fps', $SampleFps.ToString([Globalization.CultureInfo]::InvariantCulture),
    '--smoothing', $Smoothing.ToString([Globalization.CultureInfo]::InvariantCulture)
)
if ($ModelPath) {
    $motionArgs += @('--model-path', (Resolve-Path $ModelPath).Path)
}

& $PythonExecutable @motionArgs
if ($LASTEXITCODE -ne 0) {
    throw "Pose recognition failed with exit code $LASTEXITCODE"
}
if ($SkipBlender) {
    return
}

$compareScript = Join-Path $PSScriptRoot 'reconstruct_and_compare.py'
$bvhPath = Join-Path $outputPath 'motion.bvh'
$retargetPath = Join-Path $outputPath 'motion.retarget.json'
$blenderOutput = Join-Path $outputPath 'blender-comparison'
$blenderArgs = @(
    '--background', '--factory-startup',
    '--python', $compareScript, '--',
    '--bvh', $bvhPath,
    '--retarget', $retargetPath,
    '--output-dir', $blenderOutput,
    '--render'
)

if (-not $BlenderExecutable) {
    $command = Get-Command blender.exe -ErrorAction SilentlyContinue
    if ($command) {
        $BlenderExecutable = $command.Source
    }
}

if ($BlenderExecutable) {
    & $BlenderExecutable @blenderArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Blender comparison failed with exit code $LASTEXITCODE"
    }
} else {
    function Quote-Argument([string]$Value) {
        return '"' + $Value.Replace('"', '\"') + '"'
    }

    $argumentLine = ($blenderArgs | ForEach-Object { Quote-Argument ([string]$_) }) -join ' '
    & (Join-Path $PSScriptRoot 'run_msix_blender.ps1') -Arguments $argumentLine -Wait
}

$comparisonPath = Join-Path $blenderOutput 'blender-comparison.json'
$scenePath = Join-Path $blenderOutput 'pose-comparison.blend'
if (-not (Test-Path -LiteralPath $comparisonPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $scenePath -PathType Leaf)) {
    throw "Blender exited without producing the expected comparison artifacts in $blenderOutput"
}
