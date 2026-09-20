param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [string]$PackRoot = "",
    [string]$SteamRoot = ""
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mapListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"

if (-not (Test-Path $mapListPath)) {
    throw "District 12 dependency list was not found: $mapListPath"
}

function Combine-PathSafe {
    param(
        [string]$Base,
        [string]$Child
    )
    if ([string]::IsNullOrWhiteSpace($Base)) { return "" }
    try {
        return [IO.Path]::Combine($Base, $Child)
    } catch {
        return ""
    }
}

function Test-ExistingPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try {
        return (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

function Add-UniquePath {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Path
    )
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    try {
        $full = [IO.Path]::GetFullPath($Path)
    } catch {
        return
    }
    if (-not $List.Contains($full)) { $List.Add($full) }
}

function Get-SteamRoots {
    $roots = [System.Collections.Generic.List[string]]::new()

    if (-not [string]::IsNullOrWhiteSpace($SteamRoot)) {
        if (Test-ExistingPath $SteamRoot) {
            Add-UniquePath $roots $SteamRoot
        } else {
            Write-Host "[SKIP] Explicit Steam root is unavailable: $SteamRoot"
        }
    }

    $programFilesX86Steam = Combine-PathSafe ${env:ProgramFiles(x86)} "Steam"
    $programFilesSteam = Combine-PathSafe $env:ProgramFiles "Steam"
    Add-UniquePath $roots $programFilesX86Steam
    Add-UniquePath $roots $programFilesSteam

    $registryCandidates = @(
        "HKCU:\Software\Valve\Steam",
        "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam",
        "HKLM:\SOFTWARE\Valve\Steam"
    )

    foreach ($key in $registryCandidates) {
        try {
            $props = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($props.SteamPath) { Add-UniquePath $roots $props.SteamPath }
            if ($props.InstallPath) { Add-UniquePath $roots $props.InstallPath }
            if ($props.SteamExe) { Add-UniquePath $roots (Split-Path -Parent $props.SteamExe) }
        } catch {}
    }

    return $roots
}

function Get-SteamLibraries {
    param([System.Collections.Generic.List[string]]$SteamRoots)

    $libraries = [System.Collections.Generic.List[string]]::new()
    foreach ($root in $SteamRoots) {
        if (-not (Test-ExistingPath $root)) { continue }
        Add-UniquePath $libraries $root

        $vdf = Combine-PathSafe $root "steamapps\libraryfolders.vdf"
        if (-not (Test-ExistingPath $vdf)) { continue }

        try {
            $text = Get-Content -Raw -LiteralPath $vdf
            foreach ($match in [regex]::Matches($text, '"path"\s+"([^"]+)"')) {
                $path = $match.Groups[1].Value -replace '\\\\', '\'
                if (Test-ExistingPath $path) {
                    Add-UniquePath $libraries $path
                } else {
                    # Steam commonly leaves stale/offline library entries in libraryfolders.vdf.
                    # Never let one missing drive abort discovery of the libraries that are online.
                    Write-Host "[SKIP] Steam library is offline or unavailable: $path"
                }
            }
        } catch {
            Write-Host "[SKIP] Could not read Steam library list: $vdf"
        }
    }
    return $libraries
}

function Find-PackRoot {
    $candidateFileRoots = [System.Collections.Generic.List[string]]::new()

    if (-not [string]::IsNullOrWhiteSpace($PackRoot)) {
        if (Test-ExistingPath $PackRoot) {
            $resolvedPack = (Resolve-Path -LiteralPath $PackRoot).Path
            $entitybankRoot = Split-Path -Parent $resolvedPack
            $filesRoot = Split-Path -Parent $entitybankRoot
            return [pscustomobject]@{
                PackRoot = $resolvedPack
                FilesRoot = $filesRoot
                Source = "explicit -PackRoot"
            }
        }
        throw "Explicit -PackRoot does not exist or is offline: $PackRoot"
    }

    Add-UniquePath $candidateFileRoots $GameGuruFiles
    Add-UniquePath $candidateFileRoots (Combine-PathSafe $repo "Files")

    if ($env:GAMEGURU_MAX_FILES) {
        Add-UniquePath $candidateFileRoots $env:GAMEGURU_MAX_FILES
    }

    $uninstallKeys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1247290",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1247290",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1247290"
    )
    foreach ($key in $uninstallKeys) {
        try {
            $props = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($props.InstallLocation) {
                Add-UniquePath $candidateFileRoots (Combine-PathSafe $props.InstallLocation "Files")
            }
        } catch {}
    }

    $steamRoots = Get-SteamRoots
    $libraries = Get-SteamLibraries $steamRoots
    foreach ($library in $libraries) {
        if (-not (Test-ExistingPath $library)) {
            Write-Host "[SKIP] Steam library disappeared during discovery: $library"
            continue
        }

        # Use System.IO.Path.Combine instead of Join-Path here. Join-Path asks the
        # PowerShell provider to resolve the drive immediately and throws when a
        # stale Steam library points at an offline drive such as D:.
        $steamApps = Combine-PathSafe $library "steamapps"
        if ([string]::IsNullOrWhiteSpace($steamApps)) { continue }

        $manifest = Combine-PathSafe $steamApps "appmanifest_1247290.acf"
        $installDir = "GameGuru MAX"

        if (Test-ExistingPath $manifest) {
            try {
                $manifestText = Get-Content -Raw -LiteralPath $manifest
                $match = [regex]::Match($manifestText, '"installdir"\s+"([^"]+)"')
                if ($match.Success) { $installDir = $match.Groups[1].Value }
            } catch {}
        }

        Add-UniquePath $candidateFileRoots (Combine-PathSafe $steamApps "common\$installDir\Files")
        Add-UniquePath $candidateFileRoots (Combine-PathSafe $steamApps "common\GameGuru MAX\Files")
    }

    foreach ($filesRoot in $candidateFileRoots) {
        if (-not (Test-ExistingPath $filesRoot)) { continue }

        $direct = Combine-PathSafe $filesRoot "entitybank\cyberpunk streets booster pack"
        if (Test-ExistingPath $direct) {
            return [pscustomobject]@{
                PackRoot = (Resolve-Path -LiteralPath $direct).Path
                FilesRoot = (Resolve-Path -LiteralPath $filesRoot).Path
                Source = "direct Files root"
            }
        }

        $entitybank = Combine-PathSafe $filesRoot "entitybank"
        if (Test-ExistingPath $entitybank) {
            try {
                $found = Get-ChildItem -LiteralPath $entitybank -Directory -Recurse -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match '(?i)cyber.*street' } |
                    Select-Object -First 1
                if ($found) {
                    return [pscustomobject]@{
                        PackRoot = $found.FullName
                        FilesRoot = (Resolve-Path -LiteralPath $filesRoot).Path
                        Source = "recursive entitybank discovery"
                    }
                }
            } catch {}
        }
    }

    $tested = @($candidateFileRoots | ForEach-Object { "  $_" }) -join "`n"
    throw @"
Cyberpunk Streets Booster Pack could not be located automatically.

Tested GameGuru MAX Files roots:
$tested

The Documents\GameGuruApps path is the writable/user Files tree and may not contain commercial DLC assets.
The audit also checks online Steam libraries and the GameGuru MAX install location. Offline/stale Steam libraries are skipped instead of aborting discovery.

If your Steam library is nonstandard, provide the REAL mounted Steam root, for example:
  powershell -ExecutionPolicy Bypass -File .\tools\audit-cyberpunk-detail-assets.ps1 -SteamRoot "E:\SteamLibrary"

Or provide the pack folder directly:
  powershell -ExecutionPolicy Bypass -File .\tools\audit-cyberpunk-detail-assets.ps1 -PackRoot "E:\SteamLibrary\steamapps\common\GameGuru MAX\Files\entitybank\cyberpunk streets booster pack"
"@
}

$discovery = Find-PackRoot
$packRootResolved = $discovery.PackRoot
$assetFilesRoot = $discovery.FilesRoot
$mapList = (Get-Content -Raw -LiteralPath $mapListPath).ToLowerInvariant()
$all = @(Get-ChildItem -LiteralPath $packRootResolved -Filter "*.fpe" -File -Recurse | Sort-Object FullName)

$families = [ordered]@{
    "Parking posts / bollards" = { param($n) ($n -match 'parking.*post') -or ($n -match 'bollard') }
    "Pedestrian rails / parking barriers" = { param($n) (($n -match 'rail') -and ($n -notmatch 'fireescape')) -or ($n -match 'parking.*barrier') }
    "Benches" = { param($n) $n -match 'cs_bench' }
    "Bus stops" = { param($n) $n -match 'cs_bus_stop' }
    "ATMs" = { param($n) $n -match 'cs_atm' }
    "Dumpsters" = { param($n) $n -match 'cs_dumpster' }
    "Fireplugs" = { param($n) $n -match 'cs_fireplug' }
    "Air conditioners" = { param($n) $n -match 'cs_aircon' }
    "Boxes / cardboard" = { param($n) ($n -match 'cs_box_') -or ($n -match 'cs_cardboard') }
    "Newspaper clusters" = { param($n) $n -match 'cs_newspaper_cluster' }
    "Neon signs" = { param($n) $n -match 'cs_neon_' }
    "Fire escapes" = { param($n) $n -match 'cs_fireescape' }
    "Overpass pieces" = { param($n) $n -match 'cs_overpass' }
}

Write-Host "BLACK SIGNAL Cyberpunk Streets detail-asset audit"
Write-Host "Pack: $packRootResolved"
Write-Host "Asset Files root: $assetFilesRoot"
Write-Host "Discovery: $($discovery.Source)"
Write-Host "District 12 list: $mapListPath"
Write-Host "Found $($all.Count) FPE assets in the pack."
Write-Host ""

foreach ($family in $families.GetEnumerator()) {
    $matches = @()
    foreach ($file in $all) {
        $name = $file.Name.ToLowerInvariant()
        if (& $family.Value $name) {
            $relativeToFiles = $file.FullName.Substring($assetFilesRoot.Length).TrimStart('\')
            $relativeLower = $relativeToFiles.ToLowerInvariant()
            $seeded = $mapList.Contains($relativeLower)
            $matches += [pscustomobject]@{
                Asset = $relativeToFiles
                SeededInDistrict12 = $seeded
            }
        }
    }

    Write-Host "[$($family.Key)]"
    if ($matches.Count -eq 0) {
        Write-Host "  No matching .fpe files found in the installed pack."
    } else {
        foreach ($match in $matches) {
            $flag = if ($match.SeededInDistrict12) { "SEEDED" } else { "available, not seeded" }
            Write-Host "  [$flag] $($match.Asset)"
        }
    }
    Write-Host ""
}

Write-Host "How seeding works:"
Write-Host "  GameGuru MAX Lua SpawnNewEntity clones an entity already loaded by the level."
Write-Host "  For any desired optional family marked 'available, not seeded', place ONE exemplar"
Write-Host "  somewhere outside the filming/play area in BLACK SIGNAL - District 12 and save the level."
Write-Host "  Then sync the FPM back to Git. DETAIL V1 will discover and clone it automatically."
