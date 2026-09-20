param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [switch]$SkipValidation,
    [switch]$SkipStoryboardRepair
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

function Copy-ProjectOwnedFiles([string]$SourceFiles, [string]$DestinationFiles, [switch]$ExcludeProjectGameLoop) {
    if (-not (Test-Path $SourceFiles)) { return }
    New-Item -ItemType Directory -Force -Path $DestinationFiles | Out-Null

    $sourceRoot = (Resolve-Path $SourceFiles).Path.TrimEnd('\')
    Get-ChildItem -Path $sourceRoot -File -Recurse -Force | ForEach-Object {
        $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\')

        # gameloop.lua is a BLACK SIGNAL project override. Never copy it into the
        # default user Files tree here; install-default-runtime-hook.ps1 performs
        # the deliberate, backed-up global install after validation.
        if ($ExcludeProjectGameLoop -and $relative -ieq "scriptbank\gameloop.lua") {
            return
        }

        $destination = Join-Path $DestinationFiles $relative
        $destinationDir = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        Copy-Item -Force $_.FullName $destination
    }
}

function Deploy-Map([string]$MapSource, [string]$ListSource, [string]$DestinationFiles, [string]$BackupFolderName) {
    $mapName = [IO.Path]::GetFileName($MapSource)
    $listName = [IO.Path]::GetFileName($ListSource)
    $mapbank = Join-Path $DestinationFiles "mapbank"
    $mapDestination = Join-Path $mapbank $mapName
    $listDestination = Join-Path $mapbank $listName

    New-Item -ItemType Directory -Force -Path $mapbank | Out-Null

    if (Test-Path $mapDestination) {
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $backupDir = Join-Path $mapbank "$BackupFolderName\$stamp"
        New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
        Copy-Item -Force $mapDestination (Join-Path $backupDir $mapName)
        if (Test-Path $listDestination) {
            Copy-Item -Force $listDestination (Join-Path $backupDir $listName)
        }
        Write-Host "Backed up existing District 12 map to: $backupDir"
    }

    Copy-Item -Force $MapSource $mapDestination
    if (Test-Path $ListSource) {
        Copy-Item -Force $ListSource $listDestination
    }

    return $mapDestination
}

if (-not (Test-Path $GameGuruFiles)) {
    throw "GameGuru MAX user Files directory was not found: $GameGuruFiles"
}

# FPMs are versioned through Git LFS. A normal Git clone can contain only the
# tiny pointer text if LFS smudging was skipped, which GameGuru MAX cannot load.
try {
    & git -C $repo lfs pull --include="gameguru/maps/*.fpm"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "git lfs pull failed. Deployment will continue only if the FPM is already materialized."
    }
} catch {
    Write-Warning "git lfs pull could not be started: $($_.Exception.Message)"
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

if (-not (Test-Path $mapSource)) {
    throw "District 12 source map is missing: $mapSource"
}

$sourceInfo = Get-Item $mapSource
if ((Test-LfsPointer $mapSource) -or $sourceInfo.Length -lt 1MB) {
    throw "District 12 is not a materialized GameGuru FPM ($($sourceInfo.Length) bytes). Run: git lfs pull --include='gameguru/maps/*.fpm' and deploy again."
}

$projectOwnedFiles = Join-Path $repo "gameguru\Files"

# Deploy the authored FPM and project behaviours to the default GameGuru Files
# tree for direct-level testing. Physical city geometry is never synthesized here.
$globalMap = Deploy-Map -MapSource $mapSource -ListSource $listSource -DestinationFiles $GameGuruFiles -BackupFolderName "_black_signal_deploy_backups"
Copy-ProjectOwnedFiles -SourceFiles $projectOwnedFiles -DestinationFiles $GameGuruFiles -ExcludeProjectGameLoop

Write-Host ""
Write-Host "BLACK SIGNAL authored District 12 deployed to default GameGuru MAX Files."
Write-Host "Map: $globalMap"
Write-Host "Custom behaviours: $(Join-Path $GameGuruFiles 'scriptbank\user\black_signal')"

# The repository root is also the Separate Project Folder. Mirror the authored
# FPM there and retain the project-local gameloop, which intentionally does not
# generate city geometry.
$repoProjectFiles = Join-Path $repo "Files"
$repoProjectDescriptor = Join-Path $repoProjectFiles "projectbank\BLACK SIGNAL\project203.dat"
if (Test-Path $repoProjectDescriptor) {
    Write-Host ""
    Write-Host "Detected BLACK SIGNAL GameGuru MAX Separate Project Folder."

    $projectMap = Deploy-Map -MapSource $mapSource -ListSource $listName -DestinationFiles $repoProjectFiles -BackupFolderName "_black_signal_deploy_backups"
    Copy-ProjectOwnedFiles -SourceFiles $projectOwnedFiles -DestinationFiles $repoProjectFiles

    Write-Host "Project-local authored map mirror: $projectMap"
    Write-Host "Project-local behaviours: $(Join-Path $repoProjectFiles 'scriptbank\user\black_signal')"
    Write-Host "Project-local gameloop: $(Join-Path $repoProjectFiles 'scriptbank\gameloop.lua')"

    if (-not $SkipStoryboardRepair) {
        Write-Host ""
        Write-Host "Repairing BLACK SIGNAL Storyboard level binding..."
        & (Join-Path $PSScriptRoot "repair-black-signal-storyboard.ps1") -ProjectFile $repoProjectDescriptor -LevelName "mapbank\$mapName"
    } else {
        Write-Warning "Storyboard repair was skipped by request."
    }
}

$cineGuru = Join-Path $GameGuruFiles "scriptbank\Cine Guru MAX"
if (Test-Path $cineGuru) {
    Write-Host "CineGuru MAX in default Files: found"
} else {
    Write-Warning "CineGuru MAX dependency not found at: $cineGuru"
}

if (Test-Path $repoProjectDescriptor) {
    $projectCineGuru = Join-Path $repoProjectFiles "scriptbank\Cine Guru MAX"
    if (-not (Test-Path $projectCineGuru) -and (Test-Path $cineGuru)) {
        Write-Warning "CineGuru exists in default GameGuru Files but not in the Separate Project Folder. If CineGuru is absent inside MAX while this project is open, check Edit > Settings > Advanced > Writables folder location before copying any commercial dependency."
    }
}

Write-Host ""
Write-Host "Running play-level readiness diagnostics..."
& (Join-Path $PSScriptRoot "diagnose-play-level.ps1") -GameGuruFiles $GameGuruFiles
if ($LASTEXITCODE -ne 0) {
    throw "Play-level diagnostics failed. Fix the reported problem before opening MAX."
}

Write-Host ""
Write-Host "BLACK SIGNAL deployment complete."
Write-Host "District 12 is deployed and its Storyboard level binding is repaired."
Write-Host "The authored FPM is the source of truth for roads, sidewalks, buildings, skyline and street furniture."
Write-Host "Use Cyberpunk Streets snapping for physical construction and BLACK SIGNAL/CineGuru scripts only for runtime film behavior."
