param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Test-LfsPointer([string]$Path) {
    if (-not (Test-Path $Path)) { return $false }
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $buffer = New-Object byte[] 200
        $count = $stream.Read($buffer, 0, $buffer.Length)
        $text = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $count)
        return $text.StartsWith("version https://git-lfs.github.com/spec/v1")
    }
    finally {
        $stream.Dispose()
    }
}

if (-not (Test-Path $GameGuruFiles)) {
    throw "GameGuru MAX user Files directory was not found: $GameGuruFiles"
}

# FPMs are versioned through Git LFS. A normal Git clone can contain only the
# tiny pointer text if LFS smudging was skipped, which GameGuru MAX cannot load.
# Try to materialize the production map before validating or copying it.
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    & git -C $repo lfs pull --include="gameguru/maps/*.fpm"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "git lfs pull failed. Deployment will continue only if the FPM is already materialized."
    }
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

if (-not (Test-Path $mapSource)) {
    throw "District 12 source map is missing: $mapSource"
}

$sourceInfo = Get-Item $mapSource
if ((Test-LfsPointer $mapSource) -or $sourceInfo.Length -lt 1MB) {
    throw "District 12 is not a materialized GameGuru FPM ($($sourceInfo.Length) bytes). Run 'git lfs pull --include=\"gameguru/maps/*.fpm\"' and deploy again."
}

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
Write-Host "Running play-level readiness diagnostics..."
& (Join-Path $PSScriptRoot "diagnose-play-level.ps1") -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "Play-level diagnostics failed. Fix the reported problem before opening MAX."
}

Write-Host ""
Write-Host "IMPORTANT: deploying an FPM does not add it to the BLACK SIGNAL Storyboard/project."
Write-Host "For the isolation test, load 'BLACK SIGNAL - District 12.fpm' directly in the Level Editor."
Write-Host "Once Test/Play works, add that existing level to the Storyboard and save the project."
Write-Host "Use CineGuru for cinematic cameras/actors/triggers and BLACK SIGNAL scripts for project-specific metadata/glue."
