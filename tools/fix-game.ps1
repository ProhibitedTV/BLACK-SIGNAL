param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [bool]$Launch = $true
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "BLACK SIGNAL - repair, deploy, verify"
Write-Host "Repo: $repo"
Write-Host ""

$running = @(Get-Process -Name "GameGuruMAX" -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    throw "GameGuru MAX is currently running. Close it first so its in-memory Storyboard cannot overwrite the repaired project203.dat, then run this command again."
}

& (Join-Path $PSScriptRoot "deploy-gameguru-project.ps1") -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "BLACK SIGNAL deployment/repair failed."
}

Write-Host ""
Write-Host "Building and installing BLACK SIGNAL Storyboard UI..."
$projectFiles = Join-Path $repo "Files"
$projectFile = Join-Path $projectFiles "projectbank\BLACK SIGNAL\project203.dat"
& (Join-Path $PSScriptRoot "install-black-signal-ui.ps1") -ProjectFile $projectFile -ProjectFiles $projectFiles -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "BLACK SIGNAL Storyboard UI installation failed."
}

# Keep the Separate Project Folder's companion dependency list in lockstep with
# the curated authored map. This is intentionally explicit because the FPM is now
# the physical-city source of truth.
$repoList = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"
$projectMapbank = Join-Path $repo "Files\mapbank"
if ((Test-Path $repoList) -and (Test-Path $projectMapbank)) {
    Copy-Item -Force $repoList (Join-Path $projectMapbank "BLACK SIGNAL - District 12.lst")
}

Write-Host ""
Write-Host "Installing verified authored-city runtime hook in the default GameGuru scriptbank..."
& (Join-Path $PSScriptRoot "install-default-runtime-hook.ps1") -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "BLACK SIGNAL runtime-hook installation failed."
}

Write-Host ""
Write-Host "[PASS] BLACK SIGNAL is repaired and ready to open."
Write-Host "       District 12 is deployed to mapbank and bound to the existing Storyboard LEVEL node."
Write-Host "       Splash/title/loading/pause/game-over and submenu screens use the BLACK SIGNAL visual system."
Write-Host "       Runtime city spawning/dressing is disabled."
Write-Host "       The saved FPM is now the source of truth for roads, sidewalks, buildings, skyline and street furniture."
Write-Host "       Use the Cyberpunk Streets snap kit in MAX for physical city construction; reserve Lua for film/runtime behavior."

if ($Launch) {
    Write-Host "Launching GameGuru MAX through Steam..."
    Start-Process "steam://run/1247290"
} else {
    Write-Host "Launch skipped. Open the BLACK SIGNAL project in GameGuru MAX when ready."
}
