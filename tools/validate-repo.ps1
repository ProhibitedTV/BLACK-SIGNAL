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
    "docs\GAMEGURU-MAX.md",
    "docs\CINEGURU-MAX.md",
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
    if ($gameLoopContent -match 'bs_city_v2') { Write-Pass "Project gameloop hooks robust bs_city_v2 runtime" }
    else { Write-Fail "Project gameloop does not hook bs_city_v2" }

    if ($gameLoopContent -match 'Prompt\(' -and $gameLoopContent -match 'get_status') {
        Write-Pass "Project gameloop exposes temporary city-v2 runtime diagnostics"
    } else {
        Write-Fail "Project gameloop is missing city-v2 runtime diagnostics"
    }
}

$cityV2Path = Join-Path $repo "gameguru\Files\scriptbank\user\black_signal\bs_city_v2.lua"
if (Test-Path $cityV2Path) {
    $cityV2 = Get-Content -Raw $cityV2Path
    $requiredTokens = @(
        'MAX_CLONES = 900',
        'GetEntityFilePath',
        'cs_street_straight_4x.fpe',
        'cs_street_t-intersect_3.fpe',
        'cs_street_4_way_2.fpe',
        'cs_bg_building_01_floor.fpe',
        'cs_bg_building_03_floor.fpe',
        'BLACK_SIGNAL_CITY_V2_CLONES',
        'SpawnNewEntity',
        'function bs_city_v2.get_status'
    )
    foreach ($token in $requiredTokens) {
        if ($cityV2 -match [regex]::Escape($token)) { Write-Pass "City-v2 runtime includes $token" }
        else { Write-Fail "City-v2 runtime is missing $token" }
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
