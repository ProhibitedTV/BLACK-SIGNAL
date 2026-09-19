param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path $GameGuruFiles)) {
    throw "GameGuru MAX user Files directory was not found: $GameGuruFiles"
}

if (-not $SkipValidation) {
    & (Join-Path $PSScriptRoot "validate-repo.ps1") -GameGuruFiles $GameGuruFiles
    if ($LASTEXITCODE -ne 0) {
        throw "Repository validation failed. Deployment stopped."
    }
}

$mapName = "BLACK SIGNAL - District 12.fpm"
$listName = "BLACK SIGNAL - District 12.lst"
$mapSource = Join-Path $repo "gameguru\maps\$mapName"
$listSource = Join-Path $repo "gameguru\maps\$listName"
$mapbank = Join-Path $GameGuruFiles "mapbank"
$mapDestination = Join-Path $mapbank $mapName
$listDestination = Join-Path $mapbank $listName

New-Item -ItemType Directory -Force -Path $mapbank | Out-Null

if (Test-Path $mapDestination) {
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $backupDir = Join-Path $mapbank "_black_signal_deploy_backups\$stamp"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Copy-Item -Force $mapDestination (Join-Path $backupDir $mapName)
    if (Test-Path $listDestination) {
        Copy-Item -Force $listDestination (Join-Path $backupDir $listName)
    }
    Write-Host "Backed up existing District 12 map to: $backupDir"
}

Copy-Item -Force $mapSource $mapDestination
if (Test-Path $listSource) {
    Copy-Item -Force $listSource $listDestination
}

$projectFiles = Join-Path $repo "gameguru\Files"
if (Test-Path $projectFiles) {
    Get-ChildItem -Path $projectFiles -Force | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $GameGuruFiles -Recurse -Force
    }
}

Write-Host ""
Write-Host "BLACK SIGNAL deployed to GameGuru MAX."
Write-Host "Map: $mapDestination"
Write-Host "Custom behaviours: $(Join-Path $GameGuruFiles 'scriptbank\user\black_signal')"

$cineGuru = Join-Path $GameGuruFiles "scriptbank\Cine Guru MAX"
if (Test-Path $cineGuru) {
    Write-Host "CineGuru MAX: found"
} else {
    Write-Warning "CineGuru MAX dependency not found at: $cineGuru"
}

Write-Host ""
Write-Host "Open 'BLACK SIGNAL - District 12' in GameGuru MAX."
Write-Host "Use CineGuru for cinematic cameras/actors/triggers and BLACK SIGNAL scripts for project-specific metadata/glue."
