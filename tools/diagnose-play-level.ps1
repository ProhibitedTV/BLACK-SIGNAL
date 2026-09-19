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
        Fail "Repository map is only a Git LFS pointer. Run: git lfs pull --include=\"gameguru/maps/*.fpm\""
    } elseif ($sourceInfo.Length -lt 1MB) {
        Fail "Repository map is unexpectedly small ($($sourceInfo.Length) bytes). Expected a real GameGuru FPM, not a stub/pointer."
    } else {
        Pass "Repository FPM is materialized ($([math]::Round($sourceInfo.Length / 1MB, 2)) MiB)"
    }
}

if (-not (Test-Path $deployedMap)) {
    Fail "District 12 is not deployed to GameGuru MAX: $deployedMap"
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
    Pass "CineGuru MAX dependency exists"
} else {
    Warn "CineGuru MAX dependency was not found at: $cineGuru"
}

$blackSignalBehaviour = Join-Path $GameGuruFiles "scriptbank\user\black_signal\bs_shot_marker.lua"
if (Test-Path $blackSignalBehaviour) {
    Pass "BLACK SIGNAL custom behaviour is deployed"
} else {
    Warn "BLACK SIGNAL custom behaviour is not deployed yet"
}

$projectDescriptor = Join-Path $GameGuruFiles "projectbank\BLACK SIGNAL\project203.dat"
if (Test-Path $projectDescriptor) {
    Warn "A BLACK SIGNAL project descriptor exists, but this repository does not overwrite project203.dat. Opening My Games > BLACK SIGNAL is not the same as loading District 12.fpm."
    Write-Host "       For the first play test, open/load '$mapName' directly in the Level Editor, or add it as a level node in the Storyboard and save the project."
    Write-Host "       Current upstream MAX issue #6423 also reports that existing levels added to projects may not copy their files into separate project folders."
} else {
    Warn "No BLACK SIGNAL project descriptor was found under the default GameGuru MAX projectbank. Raw level test play should still work when the FPM is loaded directly."
}

Write-Host ""
Write-Host "Interpretation:"
Write-Host "- If the FPM checks fail, fix Git LFS/deployment before opening MAX."
Write-Host "- If the FPM and Player Start checks pass but Play/Test is unavailable, verify that District 12 itself is the currently loaded level, not merely the BLACK SIGNAL Storyboard/project."
Write-Host "- In MAX, use Load Existing Level / Open Level and select '$mapName' for the isolation test."
Write-Host ""
Write-Host "Diagnostics complete: $errors error(s), $warnings warning(s)."
if ($errors -gt 0) { exit 1 }
exit 0
