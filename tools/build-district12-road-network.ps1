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
$detailMap = Join-Path $outDir ($districtName + ' - road-system-v7-structural.fpm')
$detailReport = Join-Path $outDir ($districtName + ' - road-system-v7-structural.report.json')
$surfaceMap = Join-Path $outDir ($districtName + ' - road-system-v7-surface.fpm')
$surfaceReport = Join-Path $outDir ($districtName + ' - road-system-v7-surface.report.json')
$outMap = Join-Path $outDir ($districtName + ' - road-system-v8-city.fpm')
$cityReport = Join-Path $outDir ($districtName + ' - road-system-v8-city.report.json')
$validationReport = Join-Path $outDir ($districtName + ' - road-system-v8-validation.report.json')

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required.' }
$foundationTool = Join-Path $PSScriptRoot 'fpm_author_road_network_v3.py'
$detailTool = Join-Path $PSScriptRoot 'fpm_author_road_details_v7.py'
$surfaceTool = Join-Path $PSScriptRoot 'fpm_author_road_surface_v7.py'
$cityTool = Join-Path $PSScriptRoot 'fpm_author_city_mass_v2.py'
$validatorTool = Join-Path $PSScriptRoot 'fpm_validate_road_system_v7.py'

foreach ($requiredTool in @($foundationTool, $detailTool, $surfaceTool, $cityTool, $validatorTool)) {
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

Write-Host 'BLACK SIGNAL - rebuild District 12 coherent road + city system v8'
Write-Host "CyberCity donor: $cyberCity"
Write-Host "Grid: $GridSize x $GridSize"
Write-Host ''
Write-Host 'Stage 1/5: uniform road surface grammar'
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
Write-Host 'Stage 2/5: ownership-validated CyberCity structural road details'
Write-Host '  every donor detail belongs to its nearest semantically compatible road module'
Write-Host '  neighboring intersections/segments cannot contaminate exemplar profiles'
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
Write-Host 'Stage 3/5: role-aware donor-calibrated road-surface dressing'
Write-Host '  arrows/text may attach only to Straight 4X approaches'
Write-Host '  exact donor-local X/Z/Y/yaw transforms are replayed'
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
Write-Host 'Stage 4/5: compose authored city mass onto the validated road spine'
Write-Host '  building assemblies come from CyberCity donor clusters'
Write-Host '  only matching recognized full-width road families are used as anchors'
Write-Host '  the coherent road FPM remains authoritative; city mass is appended to it'
Write-Host "  output: $outMap"
Write-Host ''
Invoke-PythonStage -Tool $cityTool -ToolArguments @(
    $surfaceMap,
    $outMap,
    '--donor-fpm', $cyberCity,
    '--streetwall-clones', "$StreetwallClones",
    '--skyline-clones', "$SkylineClones",
    '--max-additions', "$MaxCityAdditions",
    '--report-json', $cityReport
) -FailureMessage 'Integrated city v2 compiler failed'

Write-Host ''
Write-Host 'Stage 5/5: fail-closed promotion validation'
Write-Host '  final city map must still match the exact planned road graph'
Write-Host '  duplicate pivots, missing roads, unexpected roads, policy regressions, or invalid approach markings abort promotion'
Write-Host ''
Invoke-PythonStage -Tool $validatorTool -ToolArguments @(
    $outMap,
    '--foundation-report', $foundationReport,
    '--detail-report', $detailReport,
    '--surface-report', $surfaceReport,
    '--report-json', $validationReport
) -FailureMessage 'Road-system v7 promotion validation failed after city composition'

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $repo ("_fpm_backups\road-system-v8-city-$stamp")
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
Write-Host '[PASS] District 12 coherent road + city system v8 promoted to project + global mapbanks.'
Write-Host '[PASS] Main streets remain one full-width road family.'
Write-Host '[PASS] Structural and surface donor ownership rules remain enforced.'
Write-Host '[PASS] Authored CyberCity building assemblies frame the road system instead of replacing it.'
Write-Host '[PASS] Final post-city validation proves the road graph was not damaged by city composition.'
Write-Host '[PASS] Production refuses to promote an empty road-only city or an invalid road/city composition.'
Write-Host "Backup: $backup"
Write-Host "Foundation report: $foundationReport"
Write-Host "Structural detail report: $detailReport"
Write-Host "Surface detail report: $surfaceReport"
Write-Host "Integrated city report: $cityReport"
Write-Host "Validation report: $validationReport"
Write-Host "SHA-256: $hash"
Write-Host '[NEXT] Start GameGuru MAX normally, open BLACK SIGNAL, and Test Play.'
Write-Host '[CHECK] Verify the reference intersection first, then one long avenue, one T, one 4-way, one curve, and the city/cliff silhouette.'
