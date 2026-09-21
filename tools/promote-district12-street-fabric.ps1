param(
    [switch]$SkipAuthor,
    [switch]$AlsoCurated,
    [switch]$ForceKnownBad
)

$ErrorActionPreference = 'Stop'

if (-not $ForceKnownBad) {
    throw @'
The first District 12 street-fabric placement pass is retired from production.
Its guessed road-local offsets produced lamp bases, rails, posts, and other props
inside traffic lanes. Use this instead:

  powershell -ExecutionPolicy Bypass -File .\tools\rebase-district12-on-cybercity.ps1

Pass -ForceKnownBad only for forensic regression testing of the old generated map.
'@
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'
$projectMap = Join-Path $repo ('Files\mapbank\' + $mapName)
$globalMap = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $mapName)
$generatedMap = Join-Path $repo '_fpm_generated\BLACK SIGNAL - District 12 - street-fabric.fpm'
$authorTool = Join-Path $PSScriptRoot 'create-district12-street-fabric.ps1'

if (-not $SkipAuthor) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $authorTool -Source Project
    if ($LASTEXITCODE -ne 0) { throw "Street-fabric authoring failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path $generatedMap)) { throw "Generated street-fabric FPM not found: $generatedMap" }
if (-not (Test-Path $projectMap)) { throw "Active project FPM not found: $projectMap" }

$backupDir = Join-Path $repo '_fpm_backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$projectBackup = Join-Path $backupDir ("BLACK SIGNAL - District 12 - project-before-street-fabric-$stamp.fpm")
Copy-Item -LiteralPath $projectMap -Destination $projectBackup -Force

if (Test-Path $globalMap) {
    $globalBackup = Join-Path $backupDir ("BLACK SIGNAL - District 12 - global-before-street-fabric-$stamp.fpm")
    Copy-Item -LiteralPath $globalMap -Destination $globalBackup -Force
}

$generatedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $generatedMap).Hash
if ((Get-Item $generatedMap).Length -lt 1024) { throw 'Generated FPM is implausibly small; refusing promotion.' }

$targets = @($projectMap, $globalMap)
if ($AlsoCurated) {
    $targets += (Join-Path $repo ('gameguru\maps\' + $mapName))
}

$promoted = @()
foreach ($target in $targets) {
    $dir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Copy-Item -LiteralPath $generatedMap -Destination $target -Force
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    if ($targetHash -ne $generatedHash) { throw "Promotion hash mismatch: $target" }
    $promoted += $target
}

Write-Host ''
Write-Host 'BLACK SIGNAL - District 12 legacy street-fabric promotion complete'
Write-Host "Project backup: $projectBackup"
if ($globalBackup) { Write-Host "Global backup:  $globalBackup" }
Write-Host "SHA-256: $generatedHash"
Write-Host 'Promoted:'
foreach ($p in $promoted) { Write-Host "  $p" }
