param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$errors = 0
$warnings = 0

function Pass([string]$m) { Write-Host "[PASS] $m" }
function Warn([string]$m) { $script:warnings++; Write-Host "[WARN] $m" }
function Fail([string]$m) { $script:errors++; Write-Host "[FAIL] $m" }

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

Write-Host "BLACK SIGNAL - GameGuru MAX play-level diagnostics"
Write-Host "Repo: $repo"
Write-Host ""

$mapName = "BLACK SIGNAL - District 12.fpm"
$listName = "BLACK SIGNAL - District 12.lst"
$sourceMap = Join-Path $repo "gameguru\maps\$mapName"
$sourceList = Join-Path $repo "gameguru\maps\$listName"
$deployedMap = Join-Path $GameGuruFiles "mapbank\$mapName"
$deployedList = Join-Path $GameGuruFiles "mapbank\$listName"

if (-not (Test-Path $sourceMap)) {
    Fail "Repository map is missing: $sourceMap"
} else {
    $sourceInfo = Get-Item $sourceMap
    if (Test-LfsPointer $sourceMap) {
        Fail "Repository map is only a Git LFS pointer. Run: git lfs pull --include='gameguru/maps/*.fpm'"
    } elseif ($sourceInfo.Length -lt 1MB) {
        Fail "Repository map is unexpectedly small ($($sourceInfo.Length) bytes). Expected a real GameGuru FPM, not a stub/pointer."
    } else {
        Pass "Repository FPM is materialized ($([math]::Round($sourceInfo.Length / 1MB, 2)) MiB)"
    }
}

if (-not (Test-Path $deployedMap)) {
    Fail "District 12 is not deployed to default GameGuru MAX Files: $deployedMap"
} else {
    $destInfo = Get-Item $deployedMap
    if (Test-LfsPointer $deployedMap) {
        Fail "The deployed GameGuru map is a Git LFS pointer, not an FPM binary. Re-run deploy after git lfs pull."
    } elseif ($destInfo.Length -lt 1MB) {
        Fail "The deployed map is unexpectedly small ($($destInfo.Length) bytes)."
    } else {
        Pass "Deployed FPM looks materialized ($([math]::Round($destInfo.Length / 1MB, 2)) MiB)"
    }
}

if ((Test-Path $sourceMap) -and (Test-Path $deployedMap) -and -not (Test-LfsPointer $sourceMap) -and -not (Test-LfsPointer $deployedMap)) {
    $sourceHash = (Get-FileHash -Algorithm SHA256 $sourceMap).Hash
    $destHash = (Get-FileHash -Algorithm SHA256 $deployedMap).Hash
    if ($sourceHash -eq $destHash) {
        Pass "Deployed FPM matches repository FPM"
    } else {
        Warn "Deployed FPM differs from repository FPM. This is expected only if you edited/saved the level in GameGuru MAX after deploying."
    }
}

if (-not (Test-Path $sourceList)) {
    Fail "Companion dependency list is missing: $sourceList"
} else {
    $listText = Get-Content -Raw $sourceList
    if ($listText -match '(?im)^entitybank\\_markers\\player start\.fpe\s*$') {
        Pass "District 12 dependency list contains the Player Start marker"
    } else {
        Warn "District 12 .lst does not list the Player Start marker. Add a Player Start marker in MAX before test play."
    }
}

$playerStartAsset = Join-Path $GameGuruFiles "entitybank\_markers\player start.fpe"
if (Test-Path $playerStartAsset) {
    Pass "GameGuru MAX Player Start asset exists"
} else {
    Fail "GameGuru MAX Player Start asset is missing: $playerStartAsset"
}

$cineGuru = Join-Path $GameGuruFiles "scriptbank\Cine Guru MAX"
if (Test-Path $cineGuru) {
    Pass "CineGuru MAX dependency exists in default Files"
} else {
    Warn "CineGuru MAX dependency was not found at: $cineGuru"
}

$blackSignalBehaviour = Join-Path $GameGuruFiles "scriptbank\user\black_signal\bs_shot_marker.lua"
if (Test-Path $blackSignalBehaviour) {
    Pass "BLACK SIGNAL custom behaviour is deployed to default Files"
} else {
    Warn "BLACK SIGNAL custom behaviour is not deployed to default Files yet"
}

$defaultProjectDescriptor = Join-Path $GameGuruFiles "projectbank\BLACK SIGNAL\project203.dat"
$repoProjectFiles = Join-Path $repo "Files"
$repoProjectDescriptor = Join-Path $repoProjectFiles "projectbank\BLACK SIGNAL\project203.dat"
$repoProjectMap = Join-Path $repoProjectFiles "mapbank\$mapName"
$repoProjectBehaviour = Join-Path $repoProjectFiles "scriptbank\user\black_signal\bs_shot_marker.lua"
$repoProjectCineGuru = Join-Path $repoProjectFiles "scriptbank\Cine Guru MAX"

if (Test-Path $defaultProjectDescriptor) {
    Warn "A BLACK SIGNAL descriptor exists under the default GameGuru MAX projectbank. Opening the project is still not the same thing as loading District 12.fpm."
}

if (Test-Path $repoProjectDescriptor) {
    Pass "Repository contains Files\projectbank\BLACK SIGNAL\project203.dat"
    Warn "This checkout looks like the GameGuru MAX Separate Project Folder / writables root, not merely a legacy export. The top-level Files tree is therefore runtime project state and must not be treated as disposable until that is confirmed in MAX."

    if (Test-Path $repoProjectMap) {
        $projectMapInfo = Get-Item $repoProjectMap
        if (Test-LfsPointer $repoProjectMap) {
            Fail "Project-local District 12 map is an LFS pointer: $repoProjectMap"
        } elseif ($projectMapInfo.Length -lt 1MB) {
            Fail "Project-local District 12 map is unexpectedly small: $repoProjectMap"
        } else {
            Pass "Project-local District 12 runtime mirror exists"
        }
    } else {
        Warn "No project-local District 12 map exists under Files\mapbank yet. If MAX's Writables folder points at this repository, run deploy-gameguru-project.ps1 after pulling the latest fix."
    }

    if (Test-Path $repoProjectBehaviour) {
        Pass "BLACK SIGNAL custom behaviour exists in the detected Separate Project Folder"
    } else {
        Warn "BLACK SIGNAL custom behaviour is missing from the detected Separate Project Folder runtime tree"
    }

    if ((Test-Path $cineGuru) -and -not (Test-Path $repoProjectCineGuru)) {
        Warn "CineGuru exists in default GameGuru Files but not inside the detected Separate Project Folder. If CineGuru is missing in MAX, verify Edit > Settings > Advanced > Writables folder location."
    }
} elseif (-not (Test-Path $defaultProjectDescriptor)) {
    Warn "No BLACK SIGNAL project descriptor was found in either the default GameGuru MAX projectbank or this repository's Files tree. Raw level test play should still work when the FPM is loaded directly."
}

Write-Host ""
Write-Host "Interpretation:"
Write-Host "- The FPM/Player Start checks prove the raw level itself is deployable; they do not prove the Storyboard has a playable level selected."
Write-Host "- If this repository is the Separate Project Folder, confirm MAX Edit > Settings > Advanced > Writables folder location points at this project root."
Write-Host "- In MAX, use Load Existing Level / Open Level and select '$mapName' for the isolation test."
Write-Host "- If direct level Test/Play works, add that existing level to the BLACK SIGNAL Storyboard and save the project."
Write-Host "- Current upstream MAX issue #6423 reports that adding existing levels to Separate Project Folder projects may fail to transfer referenced files, so keep the raw-level test as the baseline."
Write-Host ""
Write-Host "Diagnostics complete: $errors error(s), $warnings warning(s)."
if ($errors -gt 0) { exit 1 }
exit 0
