param(
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$errors = 0
$warnings = 0

function Write-Pass([string]$message) { Write-Host "[PASS] $message" }
function Write-Warn([string]$message) { $script:warnings++; Write-Host "[WARN] $message" }
function Write-Fail([string]$message) { $script:errors++; Write-Host "[FAIL] $message" }

Write-Host "BLACK SIGNAL repository validation"
Write-Host "Repo: $repo"
Write-Host ""

$required = @(
    "gameguru\maps\BLACK SIGNAL - District 12.fpm",
    "gameguru\maps\BLACK SIGNAL - District 12.lst",
    "gameguru\Files\scriptbank\gameloop.lua",
    "gameguru\Files\scriptbank\user\black_signal",
    "gameguru\Files\scriptbank\user\black_signal\bs_city_v2.lua",
    "gameguru\Files\scriptbank\user\black_signal\bs_city_v3.lua",
    "gameguru\Files\scriptbank\user\black_signal\bs_city_details.lua",
    "docs\GAMEGURU-MAX.md",
    "docs\CINEGURU-MAX.md",
    "docs\DISTRICT-12-STREET-AWARE-GENERATOR.md",
    "docs\DISTRICT-12-MODULAR-CITY-V3.md",
    "docs\DISTRICT-12-STREET-DETAILS.md",
    "ASSET-MANIFEST.md"
)

foreach ($relative in $required) {
    $path = Join-Path $repo $relative
    if (Test-Path $path) { Write-Pass $relative } else { Write-Fail "Missing $relative" }
}

$luaRoot = Join-Path $repo "gameguru\Files\scriptbank\user\black_signal"
if (Test-Path $luaRoot) {
    $scripts = @(Get-ChildItem -Path $luaRoot -Filter "*.lua" -File -Recurse)
    if ($scripts.Count -eq 0) { Write-Fail "No BLACK SIGNAL Lua behaviours found" }

    foreach ($script in $scripts) {
        $content = Get-Content -Raw -Path $script.FullName
        $base = [IO.Path]::GetFileNameWithoutExtension($script.Name)
        $escaped = [regex]::Escape($base)

        if ($content -match '(?m)^\s*--\s*DESCRIPTION:') { Write-Pass "$($script.Name): DESCRIPTION metadata" }
        else { Write-Fail "$($script.Name): missing -- DESCRIPTION metadata" }

        if ($content -match "function\s+${escaped}_init\s*\(\s*e\s*\)") { Write-Pass "$($script.Name): ${base}_init(e)" }
        else { Write-Fail "$($script.Name): filename does not have matching ${base}_init(e)" }

        if ($content -match "function\s+${escaped}_main\s*\(\s*e\s*\)") { Write-Pass "$($script.Name): ${base}_main(e)" }
        else { Write-Fail "$($script.Name): filename does not have matching ${base}_main(e)" }

        if ($content -match '(?m)^\s*--\s*DESCRIPTION:.*\[') {
            if ($content -match "function\s+${escaped}_properties\s*\(") { Write-Pass "$($script.Name): Dynamic Lua properties callback" }
            else { Write-Fail "$($script.Name): dynamic DESCRIPTION fields exist but ${base}_properties(...) is missing" }
        }
    }
}

$gameLoopPath = Join-Path $repo "gameguru\Files\scriptbank\gameloop.lua"
if (Test-Path $gameLoopPath) {
    $gameLoopContent = Get-Content -Raw $gameLoopPath
    if ($gameLoopContent -match 'bs_city_v3') { Write-Pass "Project gameloop hooks modular bs_city_v3 runtime" }
    else { Write-Fail "Project gameloop does not hook bs_city_v3" }

    if ($gameLoopContent -match 'bs_city_details') { Write-Pass "Project gameloop hooks post-city bs_city_details runtime" }
    else { Write-Fail "Project gameloop does not hook bs_city_details" }

    if ($gameLoopContent -match 'BLACK SIGNAL CITY V3' -and $gameLoopContent -match 'BLACK SIGNAL DETAIL V1' -and $gameLoopContent -match 'get_status') {
        Write-Pass "Project gameloop exposes CITY V3 and DETAIL V1 diagnostics"
    } else {
        Write-Fail "Project gameloop is missing CITY V3/DETAIL V1 diagnostics"
    }
}

$cityV3Path = Join-Path $repo "gameguru\Files\scriptbank\user\black_signal\bs_city_v3.lua"
if (Test-Path $cityV3Path) {
    $cityV3 = Get-Content -Raw $cityV3Path
    $requiredTokens = @(
        'MAX_CLONES = 850',
        'MAX_BUILDINGS = 28',
        'SPAWNS_PER_FRAME = 4',
        'SIDEWALK_BUFFER = 230',
        'ALLEY_GAP = 260',
        'GetEntityColBox',
        'GetEntityScales',
        'GetTerrainHeight',
        'GetEntityFilePath',
        'obb_overlaps',
        'footprint_from_entity',
        'footprint_from_template',
        'cs_bg_building_01_floor.fpe',
        'cs_bg_building_03_floor.fpe',
        'cs_bg_building_04_floor.fpe',
        'cs_wall_corner_01.fpe',
        'cs_walls_01_window_with_bars.fpe',
        'cs_wall_01_entry_01.fpe',
        'cs_wall_01_entry_04.fpe',
        'cs_wall_01_overhang.fpe',
        'cs_roof_tile_4x4.fpe',
        'cs_roof_tile_2x2.fpe',
        'cs_store_front_02_corner_neon_opposite.fpe',
        'shopblock',
        'midrise',
        'slab',
        'industrial',
        'needle',
        'corporate',
        'collect_parcels',
        'plan_facade',
        'plan_roof',
        'BLACK_SIGNAL_CITY_V3_BUILDINGS',
        'BLACK_SIGNAL_CITY_V3_MODULAR',
        'BLACK_SIGNAL_CITY_V3_TOWERS',
        'BLACK_SIGNAL_CITY_V3_FLOORS',
        'SpawnNewEntity',
        'function bs_city_v3.get_status'
    )
    foreach ($token in $requiredTokens) {
        if ($cityV3 -match [regex]::Escape($token)) { Write-Pass "Modular CITY V3 runtime includes $token" }
        else { Write-Fail "Modular CITY V3 runtime is missing $token" }
    }
}

$detailPath = Join-Path $repo "gameguru\Files\scriptbank\user\black_signal\bs_city_details.lua"
if (Test-Path $detailPath) {
    $details = Get-Content -Raw $detailPath
    $detailTokens = @(
        'MAX_DETAILS = 360',
        'SPAWNS_PER_FRAME = 6',
        'streets and sidewalks\\sidewalks\\',
        'parking',
        'bollard',
        'rail',
        'cs_bench.fpe',
        'cs_bus_stop.fpe',
        'cs_atm.fpe',
        'cs_dumpster_closed.fpe',
        'cs_fireplug.fpe',
        'cs_aircon_01.fpe',
        'cs_street_lamp.fpe',
        'cs_planter_01.fpe',
        'cs_trash_can.fpe',
        'place_sidewalk_details',
        'place_service_details',
        'place_small_clutter',
        'BLACK_SIGNAL_DETAILS_RAILS',
        'BLACK_SIGNAL_DETAILS_POSTS',
        'function bs_city_details.get_status'
    )
    foreach ($token in $detailTokens) {
        if ($details -match [regex]::Escape($token)) { Write-Pass "DETAIL V1 runtime includes $token" }
        else { Write-Fail "DETAIL V1 runtime is missing $token" }
    }
}

$mapListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"
if (Test-Path $mapListPath) {
    $mapList = (Get-Content -Raw $mapListPath).ToLowerInvariant()
    $requiredSeedAssets = @(
        'cs_street_straight_4x.fpe',
        'cs_street_straight_2x.fpe',
        'cs_bg_building_01_floor.fpe',
        'cs_bg_building_03_floor.fpe',
        'cs_bg_building_04_floor.fpe',
        'cs_wall_01.fpe',
        'cs_wall_corner_01.fpe',
        'cs_walls_01_window_with_bars.fpe',
        'cs_wall_01_entry_01.fpe',
        'cs_wall_01_entry_04.fpe',
        'cs_wall_01_overhang.fpe',
        'cs_roof_tile_2x2.fpe',
        'cs_roof_tile_4x4.fpe',
        'cs_store_front_02_corner_neon_opposite.fpe',
        'cs_street_lamp.fpe',
        'cs_planter_01.fpe',
        'cs_trash_can.fpe',
        'cs_bottle_can_cluster_01.fpe',
        'cs_newspaper_01.fpe'
    )
    foreach ($asset in $requiredSeedAssets) {
        if ($mapList.Contains($asset)) { Write-Pass "District 12 seeds runtime asset: $asset" }
        else { Write-Fail "District 12 list is missing required runtime seed asset: $asset" }
    }

    $optionalDetailFamilies = [ordered]@{
        'parking posts/bollards' = '(parking.*post|bollard)'
        'pedestrian rails/barriers' = '(rail|parking.*barrier)'
        'bench' = 'cs_bench\.fpe'
        'bus stop' = 'cs_bus_stop\.fpe'
        'ATM' = 'cs_atm\.fpe'
        'dumpster' = 'cs_dumpster_closed\.fpe'
        'fireplug' = 'cs_fireplug\.fpe'
        'air conditioner' = 'cs_aircon_01\.fpe'
    }
    $missingOptional = @()
    foreach ($entry in $optionalDetailFamilies.GetEnumerator()) {
        if ($mapList -match $entry.Value) { Write-Pass "District 12 seeds optional DETAIL V1 family: $($entry.Key)" }
        else { $missingOptional += $entry.Key }
    }
    if ($missingOptional.Count -gt 0) {
        Write-Warn ("Optional DETAIL V1 exemplars not yet seeded in the FPM: " + ($missingOptional -join ', ') + ". The runtime will use them automatically once one exemplar of each desired asset is present in the level.")
    }
}

try {
    $attr = (& git -C $repo check-attr filter -- "gameguru/maps/BLACK SIGNAL - District 12.fpm" 2>$null) -join "`n"
    if ($LASTEXITCODE -eq 0 -and $attr -match ': filter: lfs') { Write-Pass "District 12 .fpm uses Git LFS" }
    else { Write-Fail "District 12 .fpm is not configured for Git LFS" }
} catch {
    Write-Warn "Could not run git check-attr: $($_.Exception.Message)"
}

if (Test-Path $GameGuruFiles) {
    Write-Pass "GameGuru MAX user Files directory found"
    $cineGuru = Join-Path $GameGuruFiles "scriptbank\Cine Guru MAX"
    if (Test-Path $cineGuru) { Write-Pass "CineGuru MAX dependency found" }
    else { Write-Warn "CineGuru MAX was not found at: $cineGuru" }
} else {
    Write-Warn "GameGuru MAX user Files directory not found at: $GameGuruFiles"
}

$repoFiles = Join-Path $repo "Files"
$projectDescriptor = Join-Path $repoFiles "projectbank\BLACK SIGNAL\project203.dat"
if (Test-Path $projectDescriptor) { Write-Pass "Top-level Files/ is the BLACK SIGNAL GameGuru MAX project runtime tree" }
elseif (Test-Path $repoFiles) { Write-Warn "Top-level Files/ exists without the BLACK SIGNAL project descriptor; verify whether it is still needed" }

Write-Host ""
Write-Host "Validation complete: $errors error(s), $warnings warning(s)."
if ($errors -gt 0) { exit 1 }
exit 0
