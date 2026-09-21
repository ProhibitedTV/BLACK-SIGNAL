param(
    [switch]$SkipAuthor,
    [switch]$AlsoGlobal,
    [switch]$AlsoCurated
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'
$projectMap = Join-Path $repo ('Files\mapbank\' + $mapName)
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
$backup = Join-Path $backupDir ("BLACK SIGNAL - District 12 - before-street-fabric-$stamp.fpm")
Copy-Item -LiteralPath $projectMap -Destination $backup -Force

$generatedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $generatedMap).Hash
if ((Get-Item $generatedMap).Length -lt 1024) { throw 'Generated FPM is implausibly small; refusing promotion.' }

Copy-Item -LiteralPath $generatedMap -Destination $projectMap -Force
$projectHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $projectMap).Hash
if ($projectHash -ne $generatedHash) { throw 'Project promotion hash mismatch.' }

$promoted = @($projectMap)
if ($AlsoGlobal) {
    $globalMap = Join-Path $env:USERPROFILE ('Documents\GameGuruApps\GameGuruMAX\Files\mapbank\' + $mapName)
    $globalDir = Split-Path -Parent $globalMap
    New-Item -ItemType Directory -Force -Path $globalDir | Out-Null
    Copy-Item -LiteralPath $generatedMap -Destination $globalMap -Force
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $globalMap).Hash -ne $generatedHash) { throw 'Global promotion hash mismatch.' }
    $promoted += $globalMap
}
if ($AlsoCurated) {
    $curatedMap = Join-Path $repo ('gameguru\maps\' + $mapName)
    Copy-Item -LiteralPath $generatedMap -Destination $curatedMap -Force
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $curatedMap).Hash -ne $generatedHash) { throw 'Curated promotion hash mismatch.' }
    $promoted += $curatedMap
}

Write-Host ''
Write-Host 'BLACK SIGNAL - District 12 production promotion complete'
Write-Host "Backup: $backup"
Write-Host "SHA-256: $generatedHash"
Write-Host 'Promoted:'
foreach ($p in $promoted) { Write-Host "  $p" }
Write-Host ''
Write-Host '[NEXT] Start GameGuru MAX normally and open the BLACK SIGNAL project.'
Write-Host '[NEXT] District 12 now uses the authored street-fabric FPM in the active project mapbank.'
Write-Host '[NOTE] Re-run with -AlsoGlobal if MAX is currently resolving the global mapbank copy.'
