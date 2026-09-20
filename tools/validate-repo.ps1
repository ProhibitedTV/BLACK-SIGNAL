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
    "docs\GAMEGURU-MAX.md",
    "docs\CINEGURU-MAX.md",
    "docs\DISTRICT-12-AUTHORED-CITY.md",
    "ASSET-MANIFEST.md"
)

foreach ($relative in $required) {
    $path = Join-Path $repo $relative
    if (Test-Path $path) { Write-Pass $relative } else { Write-Fail "Missing $relative" }
}

# All BLACK SIGNAL behaviours remain syntax/metadata checked even when they are
# legacy experiments. The active gameloop decides what actually runs.
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
    }
}

$gameLoopPath = Join-Path $repo "gameguru\Files\scriptbank\gameloop.lua"
if (Test-Path $gameLoopPath) {
    $gameLoopContent = Get-Content -Raw $gameLoopPath

    if ($gameLoopContent -match 'BLACK_SIGNAL_AUTHORED_CITY' -and $gameLoopContent -match 'BLACK_SIGNAL_RUNTIME_GEOMETRY') {
        Write-Pass "Project gameloop declares authored District 12 runtime mode"
    } else {
        Write-Fail "Project gameloop is missing authored-city runtime markers"
    }

    $retiredRuntimeTokens = @(
        'bs_city_v3',
        'bs_city_details',
        'bs_curb_utilities',
        'bs_city_arch_dressing',
        'SpawnNewEntity'
    )
    foreach ($token in $retiredRuntimeTokens) {
        if ($gameLoopContent -match [regex]::Escape($token)) {
            Write-Fail "Active gameloop still references retired runtime geometry token: $token"
        } else {
            Write-Pass "Active gameloop does not reference retired runtime geometry token: $token"
        }
    }
}

$mapListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"
if (Test-Path $mapListPath) {
    $mapList = (Get-Content -Raw $mapListPath).ToLowerInvariant()

    # These are the authored snap-kit families needed to build a coherent playable
    # street in MAX. They are level dependencies, not runtime clone seeds.
    $authoredKit = [ordered]@{
        'straight road 4x' = 'cs_street_straight_4x.fpe'
        'straight road 2x' = 'cs_street_straight_2x.fpe'
        'T intersection' = 'cs_street_t-intersect_3.fpe'
        '4-way intersection' = 'cs_street_4_way_2.fpe'
        'road curve' = 'cs_street_curve_1.fpe'
        'straight sidewalk edge' = 'cs_sidewalk_straight_edge.fpe'
        'drop-curb corner' = 'cs_sidewalk_corner1_dropcurb.fpe'
        'sidewalk tile 4x4' = 'cs_sidewalk_tile_4x4.fpe'
        'wall' = 'cs_wall_01.fpe'
        'wall corner' = 'cs_wall_corner_01.fpe'
        'window wall' = 'cs_walls_01_window_with_bars.fpe'
        'entry' = 'cs_wall_01_entry_01.fpe'
        'alternate entry' = 'cs_wall_01_entry_04.fpe'
        'overhang' = 'cs_wall_01_overhang.fpe'
        'overhang corner' = 'cs_wall_01_overhang_corner.fpe'
        'roof 2x2' = 'cs_roof_tile_2x2.fpe'
        'roof 4x4' = 'cs_roof_tile_4x4.fpe'
        'shopfront window corner' = 'cs_store_front_02_corner_with_window.fpe'
        'shopfront neon corner' = 'cs_store_front_02_corner_neon_opposite.fpe'
    }

    foreach ($entry in $authoredKit.GetEnumerator()) {
        if ($mapList.Contains($entry.Value)) { Write-Pass "District 12 authored kit includes $($entry.Key): $($entry.Value)" }
        else { Write-Fail "District 12 authored kit is missing $($entry.Key): $($entry.Value)" }
    }

    $backgroundFamilies = @(
        'cs_bg_building_01_floor.fpe',
        'cs_bg_building_03_floor.fpe',
        'cs_bg_building_04_floor.fpe'
    )
    foreach ($asset in $backgroundFamilies) {
        if ($mapList.Contains($asset)) { Write-Pass "District 12 has background skyline family available: $asset" }
        else { Write-Warn "Background skyline family not currently referenced: $asset" }
    }

    if ($mapList -match 'jungle collection\\trees') {
        Write-Warn "District 12 still references Jungle Collection trees. Keep them outside the urban core or remove/occlude them where hero city shots expose raw terrain."
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
