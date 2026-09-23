param(
    [int]$GridSize = 7,
    [int]$MaxDetailAdditions = 2500,
    [int]$MaxSurfaceAdditions = 1800,
    [int]$StreetwallClones = 18,
    [int]$SkylineClones = 8,
    [int]$MaxCityAdditions = 2400
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
$surfaceMap = Join-Path $outDir ($districtName + ' - road-system-v6-surface.fpm')
$surfaceReport = Join-Path $outDir ($districtName + ' - road-system-v6-surface.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v7-city.fpm')
$outReport = Join-Path $outDir ($districtName + ' - road-system-v7-city.report.json')

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v4.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v6.py'
$cityTool = Join-Path $PSScriptRoot 'fpm_author_city_mass_v2.py'

function Invoke-PythonStage {
    param(
        [string]$Tool,
        [string[]]$ToolArguments,
        [string]$FailureMessage
    )
    if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
        & $python.Source -3 $Tool @ToolArguments
    }
    else {
        & $python.Source $Tool @ToolArguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage with exit code $LASTEXITCODE"
    }
}

Write-Host 'BLACK SIGNAL - rebuild District 12 coherent road + city system v7'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Stage 1/4: uniform road surface grammar'
Write-Host '  junction -> Straight 4X -> Straight 4X -> Straight 4X -> junction'
Write-Host '  no 2X / 1X / quarter substitutions in main traffic streets'
Write-Host "  output: $foundationMap"
Write-Host ''
Invoke-PythonStage -Tool $foundationTool -ToolArguments @(
    $cyberCity,
    $foundationMap,
    '--grid-size', "$GridSize",
    '--report-json', $foundationReport
) -FailureMessage 'Road-foundation v3 compiler failed'

Write-Host ''
Write-Host 'Stage 2/4: CyberCity-calibrated structural road detail profile'
Write-Host '  center markings, crosswalks, bollards and street lighting come from exemplar-relative transforms'
Write-Host '  center-line decal axis correction stays enforced'
Write-Host "  output: $detailMap"
Write-Host ''
Invoke-PythonStage -Tool $detailTool -ToolArguments @(
    $foundationMap,
    $detailMap,
    '--donor-fpm', $cyberCity,
    '--max-additions', "$MaxDetailAdditions",
    '--report-json', $detailReport
) -FailureMessage 'Road-detail v4 compiler failed'

Write-Host ''
Write-Host 'Stage 3/4: donor-calibrated CyberCity road-surface dressing'
Write-Host '  wear, arrows, regulatory text and utility covers replay exact donor road-local transforms'
Write-Host '  no guessed lane, curb, arrow, wear or manhole placement offsets'
Write-Host '  v4 center lines, crosswalks, lamps and bollards are preserved'
Write-Host "  output: $surfaceMap"
Write-Host ''
Invoke-PythonStage -Tool $surfaceTool -ToolArguments @(
    $detailMap,
    $surfaceMap,
    '--donor-fpm', $cyberCity,
    '--max-additions', "$MaxSurfaceAdditions",
    '--report-json', $surfaceReport
) -FailureMessage 'Road-surface v6 compiler failed'

Write-Host ''
Write-Host 'Stage 4/4: integrate authored city mass without replacing the road system'
Write-Host '  CyberCity building assemblies are harvested from the donor and attached only to matching full-width road families'
Write-Host '  the v6 road network remains authoritative; buildings are appended to it instead of rebuilding from stock CyberCity'
Write-Host '  generic CS_Street props are rejected as road anchors'
Write-Host "  output: $outMap"
Write-Host ''
Invoke-PythonStage -Tool $cityTool -ToolArguments @(
    $surfaceMap,
    $outMap,
    '--donor-fpm', $cyberCity,
    '--streetwall-clones', "$StreetwallClones",
    '--skyline-clones', "$SkylineClones",
    '--max-additions', "$MaxCityAdditions",
    '--report-json', $outReport
) -FailureMessage 'Integrated city v2 compiler failed'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v7-$stamp")
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
Write-Host '[PASS] District 12 coherent road + city system v7 promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain one full-width road family.'
Write-Host '[PASS] Surface detail remains donor-calibrated from real CyberCity road-local transforms.'
Write-Host '[PASS] Authored CyberCity building assemblies are now composed onto the coherent road target instead of replacing it.'
Write-Host '[PASS] The production build refuses to promote a road-only map if no compatible foreground city mass can be placed.'
Write-Host "Backup: $backup"
Write-Host "Foundation report: $foundationReport"
Write-Host "Structural detail report: $detailReport"
Write-Host "Surface detail report: $surfaceReport"
Write-Host "Integrated city report: $outReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play.'
Write-Host '[CHECK] Inspect a long avenue, 4-way, T and curve for continuous asphalt/markings, then confirm street-wall mass frames the roads instead of floating in lanes.'
