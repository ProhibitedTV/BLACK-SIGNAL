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
    throw "BLACK SIGNAL runtime module folder is missing: $sourceModules"
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

$requiredModules = @(
    "bs_city_v3.lua",
    "bs_city_v2.lua",
    "bs_basin_city.lua",
    "bs_city_fabric.lua",
    "bs_city_runtime.lua"
)
foreach ($module in $requiredModules) {
    $path = Join-Path $destinationModules $module
    if (-not (Test-Path $path)) {
        throw "Runtime hook installed but module is missing: $path"
    }
}

$v3Source = Join-Path $sourceModules "bs_city_v3.lua"
$v3Destination = Join-Path $destinationModules "bs_city_v3.lua"
if ((Get-FileHash -Algorithm SHA256 $v3Source).Hash -ne (Get-FileHash -Algorithm SHA256 $v3Destination).Hash) {
    throw "bs_city_v3.lua hash verification failed after copy."
}

Write-Host "[PASS] Installed BLACK SIGNAL runtime hook into default GameGuru scriptbank."
Write-Host "       Hook: $destinationGameLoop"
Write-Host "       Modules: $destinationModules"
Write-Host "[PASS] Verified modular District 12 CITY V3 runtime module."
Write-Host "       CITY V3 zones collision-safe parcels from authored roads, assembles varied modular facades and tower cores, and only activates when g_LevelFilename contains 'BLACK SIGNAL' or 'District 12'."
