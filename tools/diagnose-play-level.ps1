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

function Read-Int32At([System.IO.BinaryReader]$Reader, [long]$Offset) {
    $Reader.BaseStream.Position = $Offset
    return $Reader.ReadInt32()
}

function Read-CStringAt([System.IO.BinaryReader]$Reader, [long]$Offset, [int]$Length) {
    $Reader.BaseStream.Position = $Offset
    $bytes = $Reader.ReadBytes($Length)
    $end = [Array]::IndexOf($bytes, [byte]0)
    if ($end -lt 0) { $end = $bytes.Length }
    if ($end -eq 0) { return "" }
    return [System.Text.Encoding]::ASCII.GetString($bytes, 0, $end)
}

function Test-StoryboardBinding([string]$ProjectFile, [string]$ExpectedLevel) {
    # These values are from GameGuru MAX STORYBOARDVERSION 203.
    $expectedSize = 58930212L
    $nodeBase = 284L
    $nodeSize = 376416L
    $nodeCount = 150
    $levelNodeType = 3
    $levelNameOffset = 796L

    if (-not (Test-Path $ProjectFile)) {
        Fail "BLACK SIGNAL Storyboard is missing: $ProjectFile"
        return
    }

    $info = Get-Item $ProjectFile
    if ($info.Length -ne $expectedSize) {
        Fail "project203.dat has an unexpected size ($($info.Length) bytes; expected $expectedSize for v203)"
        return
    }

    $stream = [System.IO.File]::OpenRead($ProjectFile)
    $reader = New-Object System.IO.BinaryReader($stream, [System.Text.Encoding]::ASCII, $true)
    try {
        $sig = Read-CStringAt $reader 0 12
        $version = Read-Int32At $reader 268
        if ($sig -ne "Storyboard" -or $version -ne 203) {
            Fail "project203.dat is not a recognized GameGuru MAX v203 Storyboard (signature='$sig', version=$version)"
            return
        }

        Pass "BLACK SIGNAL project203.dat is a valid GameGuru MAX v203 Storyboard"

        $levelNodes = @()
        for ($i = 0; $i -lt $nodeCount; $i++) {
            $base = $nodeBase + ($i * $nodeSize)
            $type = Read-Int32At $reader $base
            $used = Read-Int32At $reader ($base + 20)
            if ($used -ne 0 -and $type -eq $levelNodeType) {
                $title = Read-CStringAt $reader ($base + 28) 256
                $level = Read-CStringAt $reader ($base + $levelNameOffset) 256
                $levelNodes += [pscustomobject]@{ Index = $i; Title = $title; LevelName = $level }
            }
        }

        if ($levelNodes.Count -eq 0) {
            Fail "Storyboard contains no used LEVEL node"
            return
        }

        foreach ($node in $levelNodes) {
            $shown = if ([string]::IsNullOrWhiteSpace($node.LevelName)) { "<EMPTY>" } else { $node.LevelName }
            Write-Host "       Storyboard node $($node.Index): '$($node.Title)' -> $shown"
        }

        $bound = @($levelNodes | Where-Object { $_.LevelName -ieq $ExpectedLevel })
        if ($bound.Count -gt 0) {
            Pass "Storyboard District 12 binding exists on LEVEL node $($bound[0].Index)"
        } else {
            $empty = @($levelNodes | Where-Object { [string]::IsNullOrWhiteSpace($_.LevelName) })
            if ($empty.Count -gt 0) {
                Fail "Storyboard LEVEL node is still an empty placeholder. Run tools\repair-black-signal-storyboard.ps1 with GameGuru MAX closed."
            } else {
                Fail "Storyboard has LEVEL nodes, but none point to '$ExpectedLevel'"
            }
        }
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

Write-Host "BLACK SIGNAL - GameGuru MAX play-level diagnostics"
Write-Host "Repo: $repo"
Write-Host ""

$mapName = "BLACK SIGNAL - District 12.fpm"
$listName = "BLACK SIGNAL - District 12.lst"
$storyboardLevel = "mapbank\$mapName"
$sourceMap = Join-Path $repo "gameguru\maps\$mapName"
$sourceList = Join-Path $repo "gameguru\maps\$listName"
$deployedMap = Join-Path $GameGuruFiles "mapbank\$mapName"

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

if (Test-Path $repoProjectDescriptor) {
    Pass "Repository Files tree contains the active BLACK SIGNAL project descriptor"

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
        Fail "Project-local District 12 map is missing under Files\mapbank"
    }

    Test-StoryboardBinding -ProjectFile $repoProjectDescriptor -ExpectedLevel $storyboardLevel

    if (Test-Path $repoProjectBehaviour) {
        Pass "BLACK SIGNAL custom behaviour exists in the Separate Project Folder"
    } else {
        Warn "BLACK SIGNAL custom behaviour is missing from the Separate Project Folder runtime tree"
    }

    if ((Test-Path $cineGuru) -and -not (Test-Path $repoProjectCineGuru)) {
        Warn "CineGuru exists in default GameGuru Files but not inside the Separate Project Folder. This does not prevent the Storyboard level from being playable, but verify the Writables folder before using CineGuru entities."
    }
} elseif (Test-Path $defaultProjectDescriptor) {
    Warn "BLACK SIGNAL project descriptor exists only under default GameGuru Files; this checkout does not look like the active Separate Project Folder"
    Test-StoryboardBinding -ProjectFile $defaultProjectDescriptor -ExpectedLevel $storyboardLevel
} else {
    Fail "No BLACK SIGNAL project203.dat was found, so the Storyboard cannot contain a playable level"
}

Write-Host ""
Write-Host "Diagnostics complete: $errors error(s), $warnings warning(s)."
if ($errors -gt 0) { exit 1 }
exit 0
