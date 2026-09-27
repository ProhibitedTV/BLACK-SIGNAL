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

$humanReference = Join-Path $repo ('gameguru\maps\' + $districtName + '.fpm')
$humanReferenceLst = Join-Path $repo ('gameguru\maps\' + $districtName + '.lst')
$humanDependencyOverlay = Join-Path $repo 'gameguru\buildplans\district12-v10-5-human-street-deps.lst'
if (-not (Test-Path -LiteralPath $humanReference)) {
    throw "Human-authored canonical reference is missing: $humanReference"
}
if ((Get-Item -LiteralPath $humanReference).Length -lt 1000000) {
    throw "Human-authored reference is still a Git LFS pointer. Run 'git lfs pull' and retry."
}

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
$outMap = Join-Path $outDir ($districtName + ' - road-system-v10-5-human-cityscape.fpm')
$semanticReport = Join-Path $outDir ($districtName + ' - road-system-v10-5-human-cityscape.report.json')
$validationReport = Join-Path $outDir ($districtName + ' - road-system-v10-5-validation.report.json')
$measurementFile = Join-Path $outDir 'cybercity-kit-measurements-v10-5.json'
$measurementScratch = Join-Path $outDir 'mesh-audit-v10-5'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$measureTool = Join-Path $PSScriptRoot 'measure-cybercity-kit.py'
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v7.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v7.py'
$cityTool = Join-Path $PSScriptRoot 'fpm_author_measured_city_v10_1_compat.py'
$semanticTool = Join-Path $PSScriptRoot 'fpm_author_human_cityscape_v10_5.py'
$validatorTool = Join-Path $PSScriptRoot 'fpm_validate_human_cityscape_v10_5.py'

foreach ($requiredTool in @($measureTool, $foundationTool, $detailTool, $surfaceTool, $cityTool, $semanticTool, $validatorTool)) {
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

foreach ($generated in @($foundationMap, $detailMap, $surfaceMap, $cityMap, $outMap, $foundationReport, $detailReport, $surfaceReport, $cityReport, $semanticReport, $validationReport, $measurementFile)) {
    if (Test-Path -LiteralPath $generated) { Remove-Item -LiteralPath $generated -Force }
}
if (Test-Path -LiteralPath $measurementScratch) {
    Remove-Item -LiteralPath $measurementScratch -Recurse -Force
}

Write-Host 'BLACK SIGNAL - rebuild District 12 human-authored cityscape system v10.5'
Write-Host 'Road reference: captured manual GameGuru intersection transforms'
Write-Host 'City reference: Astra measured CyberCity geometry + accepted storefront overlays'
Write-Host 'Street-life reference: captured human-authored corner, extrapolated across all validated 4-ways'
Write-Host "Human reference: $humanReference"
Write-Host "CyberCity donor:  $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Preflight: measure installed CyberCity kit including storefront modules'
Write-Host '  no commercial geometry is committed by the generator; bounds are regenerated locally'
Write-Host "  output: $measurementFile"
Write-Host ''
Invoke-PythonStage -Tool $measureTool -ToolArguments @(
    '--install', $gameGuruInstall,
    '--scratch', $measurementScratch,
    '--output', $measurementFile
) -FailureMessage 'CyberCity mesh measurement failed'

Write-Host ''
Write-Host 'Stage 1/6: uniform road surface grammar'
Write-Host '  junction -> Straight 4X -> Straight 4X -> Straight 4X -> junction'
Write-Host '  no random 2X / 1X / quarter substitutions in main traffic streets'
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
Write-Host '  temporary compatibility layer only; final semantics re-author the visible road grammar'
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
Write-Host '  final semantics removes stale donor arrows/text/wear before promotion'
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
Write-Host 'Stage 4/6: author measured Hero Block + accepted storefront facade overlays'
Write-Host '  preserve complete shells, structural corners, entries and seated roof tiles'
Write-Host '  preserve the visually accepted storefront overlay placement'
Write-Host '  preserve measured sidewalk edge/tile infill and road collision checks'
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
Write-Host 'Stage 5/6: apply road semantics + citywide human-corner grammar'
Write-Host '  exact GameGuru-authored templates come from the captured human reference; no generic carrier fallback'
Write-Host '  every validated 4-way receives rotated planter + Broad Tree + signal + trash corner grammar'
Write-Host '  four hand-spaced low curb lights are reproduced per corner'
Write-Host '  one bench per junction rotates corners deterministically to avoid prefab repetition'
Write-Host '  rejected rails, blocker posts, Joshua trees and v10.3 utility-pole dressing are omitted'
Write-Host '  T-junction/curve street furniture remains unguessed until a human reference proves that grammar'
Write-Host "  output: $outMap"
Write-Host ''
Invoke-PythonStage -Tool $semanticTool -ToolArguments @(
    $cityMap,
    $outMap,
    '--donor-fpm', $cyberCity,
    '--human-reference', $humanReference,
    '--max-additions', "$MaxSemanticAdditions",
    '--report-json', $semanticReport
) -FailureMessage 'Road-semantics v10.5 human-cityscape compiler failed'

Write-Host ''
Write-Host 'Stage 6/6: fail-closed road + human-cityscape promotion validation'
Write-Host '  exact road graph and v9.2 marking grammar must survive'
Write-Host '  every 4-way must receive the learned human corner grammar with exact template records'
Write-Host '  rejected v10.3/v10.4 props must be absent'
Write-Host ''
Invoke-PythonStage -Tool $validatorTool -ToolArguments @(
    $outMap,
    '--foundation-report', $foundationReport,
    '--semantic-report', $semanticReport,
    '--report-json', $validationReport
) -FailureMessage 'Road-system v10.5 promotion validation failed'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v10-5-human-cityscape-$stamp")
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

# Preserve the curated canonical dependency superset instead of replacing it with the
# narrower CyberCity runtime list.  Add the exact manually selected street assets as a
# small overlay, de-duplicated case-insensitively.
$lstSource = $null
if (Test-Path -LiteralPath $humanReferenceLst) {
    $lstSource = $humanReferenceLst
}
elseif (Test-Path -LiteralPath $cyberLst) {
    $lstSource = $cyberLst
}
if ($lstSource) {
    $ordered = New-Object System.Collections.Generic.List[string]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($source in @($lstSource, $humanDependencyOverlay)) {
        if (-not (Test-Path -LiteralPath $source)) { continue }
        foreach ($line in Get-Content -LiteralPath $source) {
            $value = $line.Trim()
            if ($value.Length -eq 0) { continue }
            if ($seen.Add($value)) { [void]$ordered.Add($value) }
        }
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $text = (($ordered.ToArray() -join "`r`n") + "`r`n")
    foreach ($targetLst in @($projectLst, $globalLst)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetLst) | Out-Null
        [System.IO.File]::WriteAllText($targetLst, $text, $utf8NoBom)
    }
}

Write-Host ''
Write-Host '[PASS] District 12 v10.5 human-authored cityscape promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain the exact validated full-width road graph.'
Write-Host '[PASS] Central city mass remains complete Astra-measured shells with accepted storefront overlays.'
Write-Host '[PASS] Every validated 4-way now uses the human-authored planter/tree/signal/trash/curb-light grammar.'
Write-Host '[PASS] Human street assets clone exact editor-authored ELE records; generic static material carriers are not used.'
Write-Host '[PASS] Bench placement varies deterministically one corner per junction.'
Write-Host '[PASS] Rejected rails, blocker posts, Joshua trees and v10.3 utility-pole dressing are absent.'
Write-Host '[PASS] Dynamic street-lamp markers remain restricted to exact same-version records.'
Write-Host "Backup: $backup"
Write-Host "Human reference: $humanReference"
Write-Host "Live measurement report: $measurementFile"
Write-Host "Foundation report: $foundationReport"
Write-Host "Measured-city report: $cityReport"
Write-Host "Semantic report: $semanticReport"
Write-Host "Validation report: $validationReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Open BLACK SIGNAL in GameGuru MAX and inspect several different intersections, not only the Hero Block.'
Write-Host '[CHECK] Look for correct tree/planter scale, stop-light orientation, bench variation, curb-light rhythm and material fidelity.'
