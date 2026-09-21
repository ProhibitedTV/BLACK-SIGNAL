param(
    [int]$GridSize = 7,
    [int]$MaxDetailAdditions = 2500
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

if ($GridSize -lt 5 -or ($GridSize % 2) -eq 0) {
    throw 'GridSize must be an odd integer >= 5.'
}

$outDir = Join-Path $repo '_fpm_generated'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$foundationMap = Join-Path $outDir ($districtName + ' - road-foundation-v3-base.fpm')
$foundationReport = Join-Path $outDir ($districtName + ' - road-foundation-v3-base.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v4.fpm')
$outReport = Join-Path $outDir ($districtName + ' - road-system-v4.report.json')

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v4.py'

Write-Host 'BLACK SIGNAL - rebuild District 12 coherent road system v4'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Stage 1/2: uniform road surface grammar'
Write-Host '  junction -> Straight 4X -> Straight 4X -> Straight 4X -> junction'
Write-Host '  no 2X / 1X / quarter substitutions in main traffic streets'
Write-Host "  output: $foundationMap"
Write-Host ''

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 $foundationTool $cyberCity $foundationMap --grid-size $GridSize --report-json $foundationReport
}
else {
    & $python.Source $foundationTool $cyberCity $foundationMap --grid-size $GridSize --report-json $foundationReport
}
if ($LASTEXITCODE -ne 0) { throw "Road-foundation v3 compiler failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host 'Stage 2/2: CyberCity-calibrated road detail profile'
Write-Host '  one donor profile per road kind; repeated consistently'
Write-Host '  center markings, intersection markings and street lighting come from exemplar-relative transforms'
Write-Host '  no guessed curb offsets'
Write-Host "  output: $outMap"
Write-Host ''

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 $detailTool $foundationMap $outMap --donor-fpm $cyberCity --max-additions $MaxDetailAdditions --report-json $outReport
}
else {
    & $python.Source $detailTool $foundationMap $outMap --donor-fpm $cyberCity --max-additions $MaxDetailAdditions --report-json $outReport
}
if ($LASTEXITCODE -ne 0) { throw "Road-detail v4 compiler failed with exit code $LASTEXITCODE" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v4-$stamp")
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
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash -ne $hash) {
        throw "Promotion hash mismatch: $target"
    }
}
if (Test-Path -LiteralPath $cyberLst) {
    Copy-Item -LiteralPath $cyberLst -Destination $projectLst -Force
    Copy-Item -LiteralPath $cyberLst -Destination $globalLst -Force
}

Write-Host ''
Write-Host '[PASS] District 12 coherent road system v4 promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets use one full-width surface family and one repeatable detail profile.'
Write-Host "Backup: $backup"
Write-Host "Foundation report: $foundationReport"
Write-Host "Detail report: $outReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play.'
Write-Host '[CHECK] Inspect one long avenue and one hero intersection before adding buildings.'
