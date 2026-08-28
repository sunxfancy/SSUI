param(
    [string]$ModelRoot = "models",
    [switch]$GenerationOnly
)

$ErrorActionPreference = "Stop"
$resolvedRoot = [System.IO.Path]::GetFullPath((Join-Path $PWD $ModelRoot))
$jobs = @(
    [pscustomobject]@{
        Repo = "Qwen/Qwen-Image"
        Patterns = @(
            "transformer/diffusion_pytorch_model*.safetensors",
            "text_encoder/model*.safetensors",
            "vae/diffusion_pytorch_model.safetensors",
            "tokenizer/*"
        )
    }
)
if (-not $GenerationOnly) {
    $jobs += [pscustomobject]@{
        Repo = "Qwen/Qwen-Image-Edit-2509"
        Patterns = @("transformer/diffusion_pytorch_model*.safetensors")
    }
    $jobs += [pscustomobject]@{
        Repo = "Qwen/Qwen-Image-Edit"
        Patterns = @("processor/*")
    }
}

foreach ($job in $jobs) {
    $metadata = Invoke-RestMethod "https://huggingface.co/api/models/$($job.Repo)"
    $files = @($metadata.siblings.rfilename | Where-Object {
        $filename = $_
        $job.Patterns | Where-Object { $filename -like $_ }
    } | Sort-Object -Unique)
    if ($files.Count -eq 0) {
        throw "No files matched for $($job.Repo): $($job.Patterns -join ', ')"
    }

    for ($index = 0; $index -lt $files.Count; $index++) {
        $filename = $files[$index]
        $target = Join-Path (Join-Path $resolvedRoot $job.Repo) $filename
        $targetDirectory = Split-Path -Parent $target
        [System.IO.Directory]::CreateDirectory($targetDirectory) | Out-Null
        Write-Host "[$($job.Repo) $($index + 1)/$($files.Count)] $filename"
        $url = "https://huggingface.co/$($job.Repo)/resolve/main/$filename"
        $headerLines = @(curl.exe --silent --show-error --fail --location --head $url)
        if ($LASTEXITCODE -ne 0) {
            throw "Could not read remote size for $($job.Repo)/$filename"
        }
        $lengthMatches = @(
            $headerLines | Select-String -Pattern '^content-length:\s*(\d+)\s*$'
        )
        if ($lengthMatches.Count -eq 0) {
            throw "No content length returned for $($job.Repo)/$filename"
        }
        $remoteLength = [int64]$lengthMatches[-1].Matches[0].Groups[1].Value
        if ((Test-Path -LiteralPath $target) -and
            (Get-Item -LiteralPath $target).Length -eq $remoteLength) {
            Write-Host "Already complete: $target"
            continue
        }

        $existingLength = if (Test-Path -LiteralPath $target) {
            (Get-Item -LiteralPath $target).Length
        } else {
            0
        }
        if ($existingLength -gt $remoteLength) {
            throw "Local file is larger than remote file: $target"
        }
        $remainingLength = $remoteLength - $existingLength

        if ($remainingLength -lt 256MB) {
            curl.exe `
                --fail `
                --location `
                --retry 100 `
                --retry-all-errors `
                --retry-delay 2 `
                --continue-at - `
                --output $target `
                $url
            if ($LASTEXITCODE -ne 0) {
                throw "curl failed for $($job.Repo)/$filename with exit code $LASTEXITCODE"
            }
            continue
        }

        $parallelLimit = 2
        $chunkSize = [int64]256MB
        $chunkCount = [int][math]::Ceiling($remainingLength / $chunkSize)
        $chunks = @()
        $curlArguments = @(
            "--parallel", "--parallel-max", "$parallelLimit",
            "--silent", "--show-error", "--fail", "--location",
            "--retry", "100", "--retry-all-errors", "--retry-delay", "2"
        )
        for ($chunkIndex = 0; $chunkIndex -lt $chunkCount; $chunkIndex++) {
            $start = $existingLength + ($chunkIndex * $chunkSize)
            if ($start -ge $remoteLength) {
                break
            }
            $end = [math]::Min($remoteLength - 1, $start + $chunkSize - 1)
            $part = "$target.part-$start-$end"
            $chunks += [pscustomobject]@{
                Start = $start
                End = $end
                Path = $part
            }
            if ($chunkIndex -gt 0) {
                $curlArguments += "--next"
            }
            $curlArguments += @(
                "--silent", "--show-error", "--fail", "--location",
                "--retry", "100", "--retry-all-errors", "--retry-delay", "2",
                "--range", "$start-$end", "--output", $part, $url
            )
        }

        & curl.exe @curlArguments
        if ($LASTEXITCODE -ne 0) {
            throw "parallel curl failed for $($job.Repo)/$filename with exit code $LASTEXITCODE"
        }
        foreach ($chunk in $chunks) {
            $expectedLength = $chunk.End - $chunk.Start + 1
            $actualLength = (Get-Item -LiteralPath $chunk.Path).Length
            if ($actualLength -ne $expectedLength) {
                throw "Range size mismatch for $($chunk.Path): $actualLength != $expectedLength"
            }
        }

        $output = [System.IO.File]::Open(
            $target,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $output.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null
            foreach ($chunk in ($chunks | Sort-Object Start)) {
                $input = [System.IO.File]::OpenRead($chunk.Path)
                try {
                    $input.CopyTo($output)
                } finally {
                    $input.Dispose()
                }
            }
        } finally {
            $output.Dispose()
        }
        foreach ($chunk in $chunks) {
            Remove-Item -LiteralPath $chunk.Path -Force
        }
        if ((Get-Item -LiteralPath $target).Length -ne $remoteLength) {
            throw "Assembled file has the wrong size: $target"
        }
    }
}
