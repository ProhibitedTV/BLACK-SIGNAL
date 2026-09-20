param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourceGameLoop = Join-Path $repo "gameguru\Files\scriptbank\gameloop.lua"
$destinationGameLoop = Join-Path $GameGuruFiles "scriptbank\gameloop.lua"
$sourceModules = Join-Path $repo "gameguru\Files\scriptbank\user\black_signal"
$destinationModules = Join-Path $GameGuruFiles "scriptbank\user\black_signal"

if (-not (Test-Path $GameGuruFiles)) {
    throw "GameGuru MAX Files directory was not found: $GameGuruFiles"
}
if (-not (Test-Path $sourceGameLoop)) {
    throw "BLACK SIGNAL gameloop source is missing: $sourceGameLoop"
}
if (-not (Test-Path $sourceModules)) {
    throw "BLACK SIGNAL script folder is missing: $sourceModules"
}

$destinationDir = Split-Path -Parent $destinationGameLoop
New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

$sourceHash = (Get-FileHash -Algorithm SHA256 $sourceGameLoop).Hash
if (Test-Path $destinationGameLoop) {
    $destinationHash = (Get-FileHash -Algorithm SHA256 $destinationGameLoop).Hash
    if ($destinationHash -ne $sourceHash) {
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $backupDir = Join-Path $repo ".black-signal\backups\default-gameloop\$stamp"
        New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
        Copy-Item -Force $destinationGameLoop (Join-Path $backupDir "gameloop.lua")
        Write-Host "Backed up existing default gameloop to: $backupDir"
    }
}

Copy-Item -Force $sourceGameLoop $destinationGameLoop
New-Item -ItemType Directory -Force -Path $destinationModules | Out-Null
Copy-Item -Force -Recurse (Join-Path $sourceModules "*") $destinationModules

$installedHash = (Get-FileHash -Algorithm SHA256 $destinationGameLoop).Hash
if ($installedHash -ne $sourceHash) {
    throw "Default GameGuru gameloop verification failed after copy."
}

$installedText = Get-Content -Raw $destinationGameLoop
if ($installedText -notmatch 'BLACK_SIGNAL_AUTHORED_CITY') {
    throw "Installed gameloop is not the authored-city runtime hook."
}
if ($installedText -match 'bs_city_v3|bs_city_details|bs_curb_utilities|bs_city_arch_dressing|SpawnNewEntity') {
    throw "Installed gameloop still references retired runtime city-generation code."
}

Write-Host "[PASS] Installed BLACK SIGNAL authored-city runtime hook into default GameGuru scriptbank."
Write-Host "       Hook: $destinationGameLoop"
Write-Host "       Project scripts: $destinationModules"
Write-Host "[PASS] Runtime geometry generation is disabled."
Write-Host "       District 12 physical geometry must be authored and snap-aligned in the FPM."
Write-Host "       Legacy generator scripts remain available for source-history/reference only and are not required or invoked by gameloop.lua."
Write-Host "       The hook only activates when g_LevelFilename contains 'BLACK SIGNAL' or 'District 12'."
