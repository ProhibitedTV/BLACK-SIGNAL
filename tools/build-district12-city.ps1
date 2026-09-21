param(
    [int]$StreetwallClones = 10,
    [int]$SkylineClones = 8
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$districtName = 'BLACK SIGNAL - District 12'
$projectMap = Join-Path $repo ('Files\mapbank\' + $districtName + '.fpm')
$projectLst = Join-Path $repo ('Files\mapbank\' + $districtName + '.lst')
$globalMap = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.fpm')
$globalLst = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.lst')
$cyberCity = Join-Path $env:USERPROFILE 'Documents\GameGuruApps\GameGuruMAX\Files\mapbank\CyberCity.fpm'
if (-not (Test-Path -LiteralPath $cyberCity)) {
    $cyberCity = 'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX\Files\mapbank\CyberCity.fpm'
}
if (-not (Test-Path -LiteralPath $cyberCity)) { throw 'CyberCity.fpm not found.' }
$cyberLst = [System.IO.Path]::ChangeExtension($cyberCity, '.lst')

$outDir = Join-Path $repo '_fpm_generated'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outMap = Join-Path $outDir ($districtName + ' - dense-city.fpm')
$outReport = Join-Path $outDir ($districtName + ' - dense-city.report.json')

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$tool = Join-Path $PSScriptRoot 'fpm_author_city_mass_compat.py'

Write-Host 'BLACK SIGNAL - build dense District 12 city'
Write-Host "Base: $cyberCity"
Write-Host "Output: $outMap"
Write-Host ''
if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 $tool $cyberCity $outMap --streetwall-clones $StreetwallClones --skyline-clones $SkylineClones --report-json $outReport
}
else {
    & $python.Source $tool $cyberCity $outMap --streetwall-clones $StreetwallClones --skyline-clones $SkylineClones --report-json $outReport
}
if ($LASTEXITCODE -ne 0) { throw "City compiler failed with exit code $LASTEXITCODE" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\dense-city-$stamp")
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($pair in @(
    @{ Path = $projectMap; Name = 'project-before.fpm' },
    @{ Path = $projectLst; Name = 'project-before.lst' },
    @{ Path = $globalMap; Name = 'global-before.fpm' },
    @{ Path = $globalLst; Name = 'global-before.lst' }
)) {
    if (Test-Path -LiteralPath $pair.Path) {
        Copy-Item -LiteralPath $pair.Path -Destination (Join-Path $backup $pair.Name) -Force
    }
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outMap).Hash
foreach ($target in @($projectMap, $globalMap)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $outMap -Destination $target -Force
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash -ne $hash) { throw "Promotion hash mismatch: $target" }
}
if (Test-Path -LiteralPath $cyberLst) {
    Copy-Item -LiteralPath $cyberLst -Destination $projectLst -Force
    Copy-Item -LiteralPath $cyberLst -Destination $globalLst -Force
}

Write-Host ''
Write-Host '[PASS] Dense District 12 promoted to project + global mapbanks.'
Write-Host "Backup: $backup"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play.'
