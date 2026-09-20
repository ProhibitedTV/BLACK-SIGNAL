param(
    [ValidateSet('Repo','Project','Global')]
    [string]$Source = 'Repo',
    [switch]$Json,
    [string]$ExtractDir = ''
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'

switch ($Source) {
    'Repo' {
        $fpm = Join-Path $repo 'gameguru\maps\BLACK SIGNAL - District 12.fpm'
    }
    'Project' {
        $fpm = Join-Path $repo 'Files\mapbank\BLACK SIGNAL - District 12.fpm'
    }
    'Global' {
        $fpm = Join-Path $env:USERPROFILE 'Documents\GameGuruApps\GameGuruMAX\Files\mapbank\BLACK SIGNAL - District 12.fpm'
    }
}

if (-not (Test-Path $fpm)) {
    throw "District 12 FPM not found for source '$Source': $fpm"
}

$python = $null
$pythonArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = 'py'
    $pythonArgs = @('-3')
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = 'python'
}
elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $python = 'python3'
}
else {
    throw 'Python 3 was not found on PATH (tried py, python, python3).'
}

$tool = Join-Path $PSScriptRoot 'fpm_inspect.py'

Write-Host 'BLACK SIGNAL - District 12 FPM inspection'
Write-Host "Source: $Source"
Write-Host "FPM:    $fpm"
Write-Host ''

$argsList = @()
$argsList += $pythonArgs
$argsList += $tool
$argsList += 'inspect'
$argsList += $fpm
if ($Json) { $argsList += '--json' }

& $python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "FPM inspector failed with exit code $LASTEXITCODE"
}

if ($ExtractDir -ne '') {
    $resolvedExtract = $ExtractDir
    if (-not [System.IO.Path]::IsPathRooted($resolvedExtract)) {
        $resolvedExtract = Join-Path $repo $resolvedExtract
    }
    Write-Host ''
    Write-Host "Extracting decrypted FPM members to: $resolvedExtract"
    $extractArgs = @()
    $extractArgs += $pythonArgs
    $extractArgs += $tool
    $extractArgs += 'extract'
    $extractArgs += $fpm
    $extractArgs += $resolvedExtract
    & $python @extractArgs
    if ($LASTEXITCODE -ne 0) {
        throw "FPM extraction failed with exit code $LASTEXITCODE"
    }
}
