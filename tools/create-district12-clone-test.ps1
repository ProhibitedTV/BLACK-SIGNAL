param(
    [ValidateSet('Project','Curated','Global')]
    [string]$Source = 'Project',
    [string]$Asset = 'CS_Street_Straight_4X.fpe',
    [double]$Dx = 1000.0,
    [double]$Dy = 0.0,
    [double]$Dz = 0.0,
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'

switch ($Source) {
    'Project' {
        $sourcePath = Join-Path $repo ('Files\mapbank\' + $mapName)
    }
    'Curated' {
        $sourcePath = Join-Path $repo ('gameguru\maps\' + $mapName)
    }
    'Global' {
        $sourcePath = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $mapName)
    }
}

if (-not (Test-Path $sourcePath)) {
    throw "District 12 source FPM not found: $sourcePath"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $outputDir = Join-Path $repo '_fpm_generated'
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    $OutputPath = Join-Path $outputDir 'BLACK SIGNAL - District 12 - clone-test.fpm'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repo $OutputPath
}

Write-Host 'BLACK SIGNAL - District 12 controlled FPM clone test'
Write-Host "Source mode: $Source"
Write-Host "Source FPM:  $sourcePath"
Write-Host "Output FPM:  $OutputPath"
Write-Host "Asset query: $Asset"
Write-Host ("Delta XYZ:   ({0}, {1}, {2})" -f $Dx, $Dy, $Dz)
Write-Host ''
Write-Host 'The production FPM is NOT modified. This creates a separate test artifact.'
Write-Host ''

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python 3 is required but python/py was not found on PATH.'
}

$tool = Join-Path $PSScriptRoot 'fpm_clone_entity.py'
$args = @(
    $tool,
    $sourcePath,
    $OutputPath,
    '--asset', $Asset,
    '--dx', [string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $Dx),
    '--dy', [string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $Dy),
    '--dz', [string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $Dz)
)

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 @args
}
else {
    & $python.Source @args
}
if ($LASTEXITCODE -ne 0) {
    throw "Controlled FPM clone test failed with exit code $LASTEXITCODE"
}

Write-Host ''
Write-Host '[NEXT] In GameGuru MAX, use Load Existing Level/Open Level and open ONLY the generated clone-test FPM.'
Write-Host '[NEXT] Confirm the cloned object appears at the reported new position and the level otherwise loads normally.'
Write-Host '[IMPORTANT] Do not replace the production District 12 FPM until this one-object compatibility test passes in MAX.'
