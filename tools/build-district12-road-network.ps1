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
$detailMap = Join-Path $outDir ($districtName + ' - road-system-v7-structural.fpm')
$detailReport = Join-Path $outDir ($districtName + ' - road-system-v7-structural.report.json')
$surfaceMap = Join-Path $outDir ($districtName + ' - road-system-v7-surface.fpm')
$surfaceReport = Join-Path $outDir ($districtName + ' - road-system-v7-surface.report.json')
$cityMap = Join-Path $outDir ($districtName + ' - measured-city-v10.fpm')
$cityReport = Join-Path $outDir ($districtName + ' - measured-city-v10.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v9-2-semantic.fpm')
$semanticReport = Join-Path $outDir ($districtName + ' - road-system-v9-2-semantic.report.json')
$validationReport = Join-Path $outDir ($districtName + ' - road-system-v9-2-validation.report.json')
$measurementFile = Join-Path $repo 'docs\cybercity-kit-measurements.json'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v7.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v7.py'
$cityTool = Join-Path $PSScriptRoot 'fpm_author_measured_city_v10.py'
$semanticTool = Join-Path $PSScriptRoot 'fpm_author_road_semantics_v9_compat.py'
$validatorTool = Join-Path $PSScriptRoot 'fpm_validate_road_semantics_v9_compat.py'

foreach ($requiredTool in @($foundationTool, $detailTool, $surfaceTool, $cityTool, $semanticTool, $validatorTool)) {
    if (-not (Test-Path -LiteralPath $requiredTool)) {
        throw "Required District 12 compiler/validator is missing: $requiredTool"
    }
}
if (-not (Test-Path -LiteralPath $measurementFile)) {
    throw "Astra measured kit file is missing: $measurementFile"
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

Write-Host 'BLACK SIGNAL - rebuild District 12 semantic road + measured city system v10'
Write-Host 'Road reference: captured manual GameGuru intersection transforms'
Write-Host 'City reference: Astra measured CyberCity mesh dimensions + complete Hero Block shells'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
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
Write-Host '  v9.2 later strips donor-replayed placement and rebuilds semantics from the target graph'
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
Write-Host '  v9.2 removes turn arrows/text/wear replay before final promotion'
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
Write-Host 'Stage 4/6: author Astra measured Hero Block onto the validated road graph'
Write-Host '  complete wall courses, corner modules, entries and seated roof tiles'
Write-Host '  measured sidewalk edge/tile infill; roads are preserved and collision-checked'
Write-Host '  no harvested facade slivers or pseudo-building pivot clusters'
Write-Host '  junction corners and street lamps remain owned by the semantic road stage'
Write-Host "  output: $cityMap"
Write-Host ''
Invoke-PythonStage -Tool $cityTool -ToolArguments @(
    $surfaceMap,
    $cityMap,
    '--donor-fpm', $cyberCity,
    '--measurements', $measurementFile,
    '--max-additions', "$MaxCityAdditions",
    '--report-json', $cityReport
) -FailureMessage 'Measured city v10 compiler failed'

Write-Host ''
Write-Host 'Stage 5/6: apply captured manual-reference road semantics'
Write-Host '  two road-axis-aligned center-line decals per Straight 4X module'
Write-Host '  four pivot-corrected crosswalks plus four proven sidewalk corners per 4-way'
Write-Host '  straight arrows use the measured lane offset, setback and road-facing rotation'
Write-Host '  T markings/corners remain omitted where the manual reference proves no grammar'
Write-Host '  v9.1 sparse curb lamps remain; exact dynamic markers are harvested when available'
Write-Host "  output: $outMap"
Write-Host ''
Invoke-PythonStage -Tool $semanticTool -ToolArguments @(
    $cityMap,
    $outMap,
    '--donor-fpm', $cyberCity,
    '--max-additions', "$MaxSemanticAdditions",
    '--report-json', $semanticReport
) -FailureMessage 'Road-semantics v9.2 compiler failed'

Write-Host ''
Write-Host 'Stage 6/6: fail-closed v9.2 promotion validation'
Write-Host '  exact road graph must survive measured city composition + reference-derived dressing'
Write-Host '  semantic counts must match final FPM and stale donor markings must be absent'
Write-Host ''
Invoke-PythonStage -Tool $validatorTool -ToolArguments @(
    $outMap,
    '--foundation-report', $foundationReport,
    '--semantic-report', $semanticReport,
    '--report-json', $validationReport
) -FailureMessage 'Road-system v9.2 promotion validation failed'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v10-measured-$stamp")
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
Write-Host '[PASS] District 12 semantic road + measured Hero Block system promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain the exact validated full-width road graph.'
Write-Host '[PASS] Central city mass is built from complete measured shells instead of donor pivot clusters.'
Write-Host '[PASS] Roof placement accounts for the measured +80 local-Y roof pivot.'
Write-Host '[PASS] Center-line, crosswalk, arrow and sidewalk-corner transforms come from the captured manual reference.'
Write-Host '[PASS] Street-lamp density/edge spacing remains on the visually approved v9.1 cadence.'
Write-Host '[PASS] Dynamic markers are used only when an exact same-version record is available.'
Write-Host "Backup: $backup"
Write-Host "Foundation report: $foundationReport"
Write-Host "Measured-city report: $cityReport"
Write-Host "Semantic report: $semanticReport"
Write-Host "Validation report: $validationReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play the central manually corrected intersection.'
Write-Host '[CHECK] Inspect complete building corners/roofs, sidewalk-to-road seams, crosswalk pivots, arrows, center lines and collision.'
