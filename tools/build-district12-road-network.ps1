param(
    [int]$GridSize = 7,
    [int]$MaxDetailAdditions = 2500,
    [int]$MaxSurfaceAdditions = 1800
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
$detailMap = Join-Path $outDir ($districtName + ' - road-system-v4-detail.fpm')
$detailReport = Join-Path $outDir ($districtName + ' - road-system-v4-detail.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v6.fpm')
$outReport = Join-Path $outDir ($districtName + ' - road-system-v6.report.json')

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v4.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v6.py'

Write-Host 'BLACK SIGNAL - rebuild District 12 coherent road system v6'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Stage 1/3: uniform road surface grammar'
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
Write-Host 'Stage 2/3: CyberCity-calibrated structural road detail profile'
Write-Host '  center markings, crosswalks, bollards and street lighting come from exemplar-relative transforms'
Write-Host '  center-line decal axis correction stays enforced'
Write-Host "  output: $detailMap"
Write-Host ''

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 $detailTool $foundationMap $detailMap --donor-fpm $cyberCity --max-additions $MaxDetailAdditions --report-json $detailReport
}
else {
    & $python.Source $detailTool $foundationMap $detailMap --donor-fpm $cyberCity --max-additions $MaxDetailAdditions --report-json $detailReport
}
if ($LASTEXITCODE -ne 0) { throw "Road-detail v4 compiler failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host 'Stage 3/3: donor-calibrated CyberCity road-surface dressing'
Write-Host '  wear, arrows, regulatory text and utility covers are harvested from real CyberCity placements'
Write-Host '  each surface detail replays its exact donor road-local X/Z/Y/yaw transform'
Write-Host '  no guessed lane, curb, arrow, wear or manhole placement offsets'
Write-Host '  v4 center lines, crosswalks, lamps and bollards are preserved'
Write-Host "  output: $outMap"
Write-Host ''

if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
    & $python.Source -3 $surfaceTool $detailMap $outMap --donor-fpm $cyberCity --max-additions $MaxSurfaceAdditions --report-json $outReport
}
else {
    & $python.Source $surfaceTool $detailMap $outMap --donor-fpm $cyberCity --max-additions $MaxSurfaceAdditions --report-json $outReport
}
if ($LASTEXITCODE -ne 0) { throw "Road-surface v6 compiler failed with exit code $LASTEXITCODE" }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v6-$stamp")
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
Write-Host '[PASS] District 12 coherent road system v6 promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain one full-width road family.'
Write-Host '[PASS] Surface detail is donor-calibrated from real CyberCity road-local transforms.'
Write-Host '[PASS] v5 guessed decal placement is no longer used by the production build.'
Write-Host "Backup: $backup"
Write-Host "Foundation report: $foundationReport"
Write-Host "Structural detail report: $detailReport"
Write-Host "Surface detail report: $outReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play.'
Write-Host '[CHECK] Verify wear/marking/manhole details sit on asphalt on a long avenue, 4-way, T, and curve.'
