param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packRoot = Join-Path $GameGuruFiles "entitybank\cyberpunk streets booster pack"
$mapListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"

if (-not (Test-Path $packRoot)) {
    throw "Cyberpunk Streets Booster Pack was not found at: $packRoot"
}
if (-not (Test-Path $mapListPath)) {
    throw "District 12 dependency list was not found: $mapListPath"
}

$mapList = (Get-Content -Raw $mapListPath).ToLowerInvariant()
$all = @(Get-ChildItem -Path $packRoot -Filter "*.fpe" -File -Recurse | Sort-Object FullName)

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
Write-Host "Pack: $packRoot"
Write-Host "District 12 list: $mapListPath"
Write-Host ""

foreach ($family in $families.GetEnumerator()) {
    $matches = @()
    foreach ($file in $all) {
        $name = $file.Name.ToLowerInvariant()
        if (& $family.Value $name) {
            $relativeToFiles = $file.FullName.Substring($GameGuruFiles.Length).TrimStart('\')
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
