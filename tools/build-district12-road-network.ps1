param(
    [int]$GridSize = 7,
    [int]$MaxDetailAdditions = 2500,
    [int]$MaxSurfaceAdditions = 1800,
    [int]$MaxSemanticAdditions = 2200,
    [int]$StreetwallClones = 14,
    [int]$SkylineClones = 4,
    [int]$MaxCityAdditions = 1200
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$districtName = 'BLACK SIGNAL - District 12'
$projectMap = Join-Path $repo ('Files\mapbank\' + $districtName + '.fpm')
$projectLst = Join-Path $repo ('Files\mapbank\' + $districtName + '.lst')
$globalMap = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.fpm')
$globalLst = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.lst')
$gameGuruInstall = 'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX'
$cyberCity = Join-Path $env:USERPROFILE 'Documents\GameGuruApps\GameGuruMAX\Files\mapbank\CyberCity.fpm'
if (-not (Test-Path -LiteralPath $cyberCity)) {
    $cyberCity = Join-Path $gameGuruInstall 'Files\mapbank\CyberCity.fpm'
}
if (-not (Test-Path -LiteralPath $cyberCity)) { throw 'CyberCity.fpm not found.' }
if (-not (Test-Path -LiteralPath $gameGuruInstall)) { throw "GameGuru MAX install not found: $gameGuruInstall" }
$cyberLst = [System.IO.Path]::ChangeExtension($cyberCity, '.lst')

if ($GridSize -lt 5 -or ($GridSize % 2) -eq 0) {
    throw 'GridSize must be an odd integer >= 5.'
}

$outDir = Join-Path $repo '_fpm_generated'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$foundationMap = Join-Path $outDir ($districtName + ' - road-foundation-v3-base.fpm')
$foundationReport = Join-Path $outDir ($districtName + ' - road-foundation-v3-base.report.json')
$detailMap = Join-Path $outDir ($districtName + ' - road-system-v7-structural.fpm')
$detailReport = Join-Path $outDir ($districtName + ' - road-system-v7-structural.report.json')
$surfaceMap = Join-Path $outDir ($districtName + ' - road-system-v7-surface.fpm')
$surfaceReport = Join-Path $outDir ($districtName + ' - road-system-v7-surface.report.json')
$cityMap = Join-Path $outDir ($districtName + ' - measured-city-v10-2-storefront-overlay.fpm')
$cityReport = Join-Path $outDir ($districtName + ' - measured-city-v10-2-storefront-overlay.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v10-4-streetlife.fpm')
$semanticReport = Join-Path $outDir ($districtName + ' - road-system-v10-4-streetlife.report.json')
$validationReport = Join-Path $outDir ($districtName + ' - road-system-v10-4-validation.report.json')
$measurementFile = Join-Path $outDir 'cybercity-kit-measurements-v10-4.json'
$measurementScratch = Join-Path $outDir 'mesh-audit-v10-4'
$streetlifeAssetFile = Join-Path $outDir 'streetlife-assets-v10-4.json'
$streetlifeScratch = Join-Path $outDir 'streetlife-audit-v10-4'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$measureTool = Join-Path $PSScriptRoot 'measure-cybercity-kit.py'
$streetlifeDiscoverTool = Join-Path $PSScriptRoot 'discover-streetlife-assets.py'
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v7.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v7.py'
$cityTool = Join-Path $PSScriptRoot 'fpm_author_measured_city_v10_1_compat.py'
$semanticTool = Join-Path $PSScriptRoot 'fpm_author_streetlife_v10_4.py'
$validatorTool = Join-Path $PSScriptRoot 'fpm_validate_streetlife_v10_4.py'

foreach ($requiredTool in @($measureTool, $streetlifeDiscoverTool, $foundationTool, $detailTool, $surfaceTool, $cityTool, $semanticTool, $validatorTool)) {
    if (-not (Test-Path -LiteralPath $requiredTool)) {
        throw "Required District 12 compiler/validator is missing: $requiredTool"
    }
}

function Invoke-PythonStage {
    param(
        [Parameter(Mandatory=$true)][string]$Tool,
        [Parameter(Mandatory=$true)][string[]]$ToolArguments,
        [Parameter(Mandatory=$true)][string]$FailureMessage
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

foreach ($generated in @($foundationMap, $detailMap, $surfaceMap, $cityMap, $outMap, $foundationReport, $detailReport, $surfaceReport, $cityReport, $semanticReport, $validationReport, $measurementFile, $streetlifeAssetFile)) {
    if (Test-Path -LiteralPath $generated) { Remove-Item -LiteralPath $generated -Force }
}
foreach ($scratch in @($measurementScratch, $streetlifeScratch)) {
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
}

Write-Host 'BLACK SIGNAL - rebuild District 12 filmable street-life system v10.4'
Write-Host 'Road reference: captured manual GameGuru intersection transforms'
Write-Host 'City reference: Astra measured CyberCity geometry + complete Hero Block shells'
Write-Host 'Street-level pass: accepted storefront overlays + sparse infrastructure + measured urban greenery'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Preflight A: measure installed CyberCity kit including storefront modules'
Write-Host '  no commercial geometry is committed; bounds are regenerated from the installed DLC'
Write-Host "  output: $measurementFile"
Write-Host ''
Invoke-PythonStage -Tool $measureTool -ToolArguments @(
    '--install', $gameGuruInstall,
    '--scratch', $measurementScratch,
    '--output', $measurementFile
) -FailureMessage 'CyberCity mesh measurement failed'

Write-Host ''
Write-Host 'Preflight B: discover + measure installed street-life vegetation'
Write-Host '  prefer a Cyberpunk Streets planter and a compact measured city-tree candidate'
Write-Host '  only asset paths/bounds are recorded; no third-party geometry enters the repo'
Write-Host "  output: $streetlifeAssetFile"
Write-Host ''
Invoke-PythonStage -Tool $streetlifeDiscoverTool -ToolArguments @(
    '--install', $gameGuruInstall,
    '--scratch', $streetlifeScratch,
    '--output', $streetlifeAssetFile
) -FailureMessage 'Street-life asset discovery failed'

Write-Host ''
Write-Host 'Stage 1/6: uniform road surface grammar'
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
Write-Host 'Stage 2/6: harvest safe structural templates from CyberCity'
Write-Host '  this temporary layer supplies exact same-version decal/lamp/light records'
Write-Host '  the semantic pass later strips donor-replayed placement and rebuilds from the target graph'
Write-Host "  output: $detailMap"
Write-Host ''
Invoke-PythonStage -Tool $detailTool -ToolArguments @(
    $foundationMap,
    $detailMap,
    '--donor-fpm', $cyberCity,
    '--max-additions', "$MaxDetailAdditions",
    '--report-json', $detailReport
) -FailureMessage 'Road-detail v7 compiler failed'

Write-Host ''
Write-Host 'Stage 3/6: harvest donor surface templates'
Write-Host '  this remains an intermediate compatibility source only'
Write-Host '  final semantics removes turn arrows/text/wear replay before promotion'
Write-Host "  output: $surfaceMap"
Write-Host ''
Invoke-PythonStage -Tool $surfaceTool -ToolArguments @(
    $detailMap,
    $surfaceMap,
    '--donor-fpm', $cyberCity,
    '--max-additions', "$MaxSurfaceAdditions",
    '--report-json', $surfaceReport
) -FailureMessage 'Road-surface v7 compiler failed'

Write-Host ''
Write-Host 'Stage 4/6: author measured Hero Block + storefront facade overlays'
Write-Host '  preserve complete wall courses, structural ground-floor corners and seated roof tiles'
Write-Host '  overlay measured shopfront geometry; do not cut holes in the Astra shell'
Write-Host '  preserve measured sidewalk edge/tile infill and collision-check against the road graph'
Write-Host '  rejected neon/signage variant stays excluded pending independent sign calibration'
Write-Host "  output: $cityMap"
Write-Host ''
Invoke-PythonStage -Tool $cityTool -ToolArguments @(
    $surfaceMap,
    $cityMap,
    '--donor-fpm', $cyberCity,
    '--measurements', $measurementFile,
    '--max-additions', "$MaxCityAdditions",
    '--report-json', $cityReport
) -FailureMessage 'Measured city v10.2 compiler failed'

Write-Host ''
Write-Host 'Stage 5/6: apply road semantics + Hero Block street-life dressing'
Write-Host '  retain the validated v10.3 bollards, curb guards, sidewalk lights and sparse utility poles'
Write-Host '  add 8 paired measured planters/city trees in controlled sidewalk zones'
Write-Host '  add 8 low planter accent lights shifted toward the curb for camera depth'
Write-Host '  keep road geometry, storefronts, entries and crosswalk approaches clear'
Write-Host '  all street-life placements are deterministic; no random scatter'
Write-Host "  output: $outMap"
Write-Host ''
Invoke-PythonStage -Tool $semanticTool -ToolArguments @(
    $cityMap,
    $outMap,
    '--donor-fpm', $cyberCity,
    '--streetlife-assets', $streetlifeAssetFile,
    '--max-additions', "$MaxSemanticAdditions",
    '--report-json', $semanticReport
) -FailureMessage 'Road-semantics v10.4 street-life compiler failed'

Write-Host ''
Write-Host 'Stage 6/6: fail-closed road + street-life promotion validation'
Write-Host '  exact road graph and v9.2 marking grammar must survive'
Write-Host '  v10.3 infrastructure and v10.4 planter/tree/light counts must match the final FPM exactly'
Write-Host ''
Invoke-PythonStage -Tool $validatorTool -ToolArguments @(
    $outMap,
    '--foundation-report', $foundationReport,
    '--semantic-report', $semanticReport,
    '--streetlife-assets', $streetlifeAssetFile,
    '--report-json', $validationReport
) -FailureMessage 'Road-system v10.4 promotion validation failed'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v10-4-streetlife-$stamp")
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
Write-Host '[PASS] District 12 v10.4 filmable street-life block promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain the exact validated full-width road graph.'
Write-Host '[PASS] Central city mass remains complete Astra-measured shells.'
Write-Host '[PASS] Storefront geometry remains an overlay; structural ground-floor corners are preserved.'
Write-Host '[PASS] Existing bollards, rails, low sidewalk lights, utility poles and sparse street lamps remain controlled.'
Write-Host '[PASS] Eight measured planter/tree pairs now add urban greenery without blocking filming paths.'
Write-Host '[PASS] Eight low planter accent lights add pedestrian-scale night depth without increasing street-lamp density.'
Write-Host '[PASS] Dynamic markers are used only when an exact same-version record is available.'
Write-Host "Backup: $backup"
Write-Host "Live measurement report: $measurementFile"
Write-Host "Street-life discovery report: $streetlifeAssetFile"
Write-Host "Foundation report: $foundationReport"
Write-Host "Measured-city report: $cityReport"
Write-Host "Semantic report: $semanticReport"
Write-Host "Validation report: $validationReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play the central Hero Block.'
Write-Host '[CHECK] Inspect planter/tree scale, pedestrian clearance, accent-light placement, storefront visibility and overall filming composition.'
