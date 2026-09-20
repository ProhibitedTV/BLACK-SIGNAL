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
    "bs_city_details.lua",
    "bs_curb_utilities.lua",
    "bs_city_arch_dressing.lua",
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

$verifiedModules = @("bs_city_v3.lua", "bs_city_details.lua", "bs_curb_utilities.lua", "bs_city_arch_dressing.lua")
foreach ($module in $verifiedModules) {
    $src = Join-Path $sourceModules $module
    $dst = Join-Path $destinationModules $module
    if ((Get-FileHash -Algorithm SHA256 $src).Hash -ne (Get-FileHash -Algorithm SHA256 $dst).Hash) {
        throw "$module hash verification failed after copy."
    }
}

Write-Host "[PASS] Installed BLACK SIGNAL runtime hook into default GameGuru scriptbank."
Write-Host "       Hook: $destinationGameLoop"
Write-Host "       Modules: $destinationModules"
Write-Host "[PASS] Verified CITY V3, DETAIL V1, CURB V1, and ARCH V1 runtime modules."
Write-Host "       CITY V3 builds collision-safe architecture; DETAIL V1 dresses streets/service edges; CURB V1 uses exact seeded guards/dividers/lights/planters/poles; ARCH V1 adds facade and rooftop dressing."
Write-Host "       All passes only activate when g_LevelFilename contains 'BLACK SIGNAL' or 'District 12'."
