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
Write-Host "Installing verified runtime hook in the default GameGuru scriptbank..."
& (Join-Path $PSScriptRoot "install-default-runtime-hook.ps1") -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "BLACK SIGNAL runtime-hook installation failed."
}

Write-Host ""
Write-Host "[PASS] BLACK SIGNAL is repaired and ready to open."
Write-Host "       District 12 is deployed to mapbank and bound to the existing Storyboard LEVEL node."
Write-Host "       The city runtime is installed in both the project tree and the default GameGuru scriptbank."
Write-Host "       The default hook is level-gated and stays inert outside BLACK SIGNAL / District 12."

if ($Launch) {
    Write-Host "Launching GameGuru MAX through Steam..."
    Start-Process "steam://run/1247290"
} else {
    Write-Host "Launch skipped. Open the BLACK SIGNAL project in GameGuru MAX when ready."
}
