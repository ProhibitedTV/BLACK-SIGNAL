param(
    [string]$CyberCityPath = '',
    [switch]$ProjectOnly,
    [switch]$SkipInspect
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$districtName = 'BLACK SIGNAL - District 12'
$projectMap = Join-Path $repo ('Files\mapbank\' + $districtName + '.fpm')
$projectLst = Join-Path $repo ('Files\mapbank\' + $districtName + '.lst')
$globalMap = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.fpm')
$globalLst = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $districtName + '.lst')

function Resolve-CyberCitySource {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath)) {
            throw "CyberCity donor FPM not found: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE 'Documents\GameGuruApps\GameGuruMAX\Files\mapbank\CyberCity.fpm'),
        'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX\Files\mapbank\CyberCity.fpm',
        'C:\Program Files\Steam\steamapps\common\GameGuru MAX\Files\mapbank\CyberCity.fpm'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'CyberCity.fpm was not found in the normal GameGuru MAX mapbanks. Pass -CyberCityPath explicitly if it is installed elsewhere.'
}

function Backup-IfPresent {
    param(
        [string]$Path,
        [string]$DestinationDirectory
    )
    if (-not (Test-Path -LiteralPath $Path)) { return }
    New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
    Copy-Item -LiteralPath $Path -Destination (Join-Path $DestinationDirectory ([System.IO.Path]::GetFileName($Path))) -Force
}

function Copy-And-Verify {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$ExpectedHash
    )
    $destinationDir = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash
    if ($actualHash -ne $ExpectedHash) {
        throw "Copy verification failed for $Destination"
    }
}

$sourceMap = Resolve-CyberCitySource -ExplicitPath $CyberCityPath
$sourceLst = [System.IO.Path]::ChangeExtension($sourceMap, '.lst')
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceMap).Hash
$sourceLength = (Get-Item -LiteralPath $sourceMap).Length

if ($sourceLength -lt 1024) {
    throw 'CyberCity donor FPM is implausibly small; refusing to use it.'
}

Write-Host 'BLACK SIGNAL - rebase District 12 on the official CyberCity exemplar'
Write-Host "CyberCity source: $sourceMap"
Write-Host "Source SHA-256:  $sourceHash"
Write-Host ''
Write-Host 'Why this exists:'
Write-Host '  - stop guessing curb offsets and prop cadence'
Write-Host '  - use the installed Cyber City Streets showcase map as spatial ground truth'
Write-Host '  - get District 12 back to a coherent authored cyber-city baseline first'
Write-Host ''

if (-not $SkipInspect) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $python) { throw 'Python 3 is required for the FPM integrity inspection.' }

    $inspector = Join-Path $PSScriptRoot 'fpm_inspect.py'
    Write-Host 'Inspecting donor FPM before promotion...'
    if ($python.Name -ieq 'py.exe' -or $python.Name -ieq 'py') {
        & $python.Source -3 $inspector inspect $sourceMap
    }
    else {
        & $python.Source $inspector inspect $sourceMap
    }
    if ($LASTEXITCODE -ne 0) {
        throw "CyberCity donor failed FPM inspection with exit code $LASTEXITCODE"
    }
    Write-Host ''
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $repo ("_fpm_backups\cybercity-rebase-$stamp")
Backup-IfPresent -Path $projectMap -DestinationDirectory (Join-Path $backupRoot 'project')
Backup-IfPresent -Path $projectLst -DestinationDirectory (Join-Path $backupRoot 'project')
if (-not $ProjectOnly) {
    Backup-IfPresent -Path $globalMap -DestinationDirectory (Join-Path $backupRoot 'global')
    Backup-IfPresent -Path $globalLst -DestinationDirectory (Join-Path $backupRoot 'global')
}

Copy-And-Verify -Source $sourceMap -Destination $projectMap -ExpectedHash $sourceHash
if (Test-Path -LiteralPath $sourceLst) {
    Copy-Item -LiteralPath $sourceLst -Destination $projectLst -Force
}
else {
    Write-Warning "CyberCity companion LST was not found: $sourceLst"
}

$promoted = @($projectMap)
if (-not $ProjectOnly) {
    Copy-And-Verify -Source $sourceMap -Destination $globalMap -ExpectedHash $sourceHash
    if (Test-Path -LiteralPath $sourceLst) {
        Copy-Item -LiteralPath $sourceLst -Destination $globalLst -Force
    }
    $promoted += $globalMap
}

Write-Host ''
Write-Host 'District 12 CyberCity rebase complete.'
Write-Host "Backup root: $backupRoot"
Write-Host 'Promoted local runtime maps:'
foreach ($path in $promoted) { Write-Host "  $path" }
Write-Host ''
Write-Host '[NEXT] Start GameGuru MAX normally and open the BLACK SIGNAL project.'
Write-Host '[NEXT] Test Play District 12 and capture one street-level screenshot.'
Write-Host '[IMPORTANT] The tracked gameguru\maps FPM is intentionally NOT modified.'
Write-Host '[IMPORTANT] Cyber City Streets DLC binaries remain local and are never committed to this public repository.'
