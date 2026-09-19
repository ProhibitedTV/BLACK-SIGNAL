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

function Copy-ProjectOwnedFiles([string]$SourceFiles, [string]$DestinationFiles) {
    if (-not (Test-Path $SourceFiles)) { return }
    New-Item -ItemType Directory -Force -Path $DestinationFiles | Out-Null
    Get-ChildItem -Path $SourceFiles -Force | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $DestinationFiles -Recurse -Force
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

if (-not (Test-Path $mapSource)) {
    throw "District 12 source map is missing: $mapSource"
}

$sourceInfo = Get-Item $mapSource
if ((Test-LfsPointer $mapSource) -or $sourceInfo.Length -lt 1MB) {
    throw "District 12 is not a materialized GameGuru FPM ($($sourceInfo.Length) bytes). Run: git lfs pull --include='gameguru/maps/*.fpm' and deploy again."
}

$projectOwnedFiles = Join-Path $repo "gameguru\Files"

# Always deploy to the default GameGuru MAX user Files tree. This gives us a
# known-good raw-level isolation path even when the project/storyboard is broken.
$globalMap = Deploy-Map -MapSource $mapSource -ListSource $listSource -DestinationFiles $GameGuruFiles -BackupFolderName "_black_signal_deploy_backups"
Copy-ProjectOwnedFiles -SourceFiles $projectOwnedFiles -DestinationFiles $GameGuruFiles

Write-Host ""
Write-Host "BLACK SIGNAL deployed to default GameGuru MAX Files."
Write-Host "Map: $globalMap"
Write-Host "Custom behaviours: $(Join-Path $GameGuruFiles 'scriptbank\user\black_signal')"

# The original BLACK SIGNAL checkout contains Files/projectbank/BLACK SIGNAL/
# project203.dat. That shape is consistent with a MAX Separate Project Folder.
# If present, also maintain a local runtime mirror inside that project Files tree.
# The curated source still lives under gameguru/; these copied runtime files are
# ignored by Git so we do not duplicate source or vendor third-party content.
$repoProjectFiles = Join-Path $repo "Files"
$repoProjectDescriptor = Join-Path $repoProjectFiles "projectbank\BLACK SIGNAL\project203.dat"
if (Test-Path $repoProjectDescriptor) {
    Write-Host ""
    Write-Host "Detected BLACK SIGNAL project state inside the repository Files tree."
    Write-Host "Treating the checkout as a likely GameGuru MAX Separate Project Folder runtime root."

    $projectMap = Deploy-Map -MapSource $mapSource -ListSource $listSource -DestinationFiles $repoProjectFiles -BackupFolderName "_black_signal_deploy_backups"
    Copy-ProjectOwnedFiles -SourceFiles $projectOwnedFiles -DestinationFiles $repoProjectFiles

    Write-Host "Project-local map mirror: $projectMap"
    Write-Host "Project-local behaviours: $(Join-Path $repoProjectFiles 'scriptbank\user\black_signal')"
    Write-Warning "This does NOT edit project203.dat or attach District 12 to the Storyboard. Load the FPM directly first, then add it to the Storyboard in MAX."
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
        Write-Warning "CineGuru exists in the default Files tree but not in the detected Separate Project Folder. If CineGuru is absent inside MAX while this project is open, check Edit > Settings > Advanced > Writables folder location before copying any commercial dependency."
    }
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
