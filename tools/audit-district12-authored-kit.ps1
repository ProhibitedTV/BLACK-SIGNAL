param(
    [string]$ListPath = ""
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ListPath)) {
    $ListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"
}
if (-not (Test-Path $ListPath)) {
    throw "District 12 dependency list not found: $ListPath"
}

$lines = @(Get-Content $ListPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '\.fpe$' })
$pack = @($lines | Where-Object { $_ -match '(?i)entitybank\\cyberpunk streets booster pack\\' } | Sort-Object -Unique)

function Group-Assets([string]$Pattern) {
    return @($pack | Where-Object { $_ -match $Pattern } | Sort-Object)
}

$groups = [ordered]@{
    "Road sections" = Group-Assets '(?i)\\streets and sidewalks\\streets\\'
    "Pavement / sidewalks" = Group-Assets '(?i)\\streets and sidewalks\\sidewalks\\'
    "Road markings / decals" = Group-Assets '(?i)\\streets and sidewalks\\street decals\\'
    "Modular building pieces" = Group-Assets '(?i)\\buildings\\'
    "Shop fronts / signs" = Group-Assets '(?i)\\store fronts\\'
    "Background buildings" = Group-Assets '(?i)\\background buildings\\'
    "Street / sidewalk props" = Group-Assets '(?i)\\misc\\sidewalk misc\\'
    "General props" = Group-Assets '(?i)\\misc\\general misc\\'
    "Building misc / rooftop" = Group-Assets '(?i)\\misc\\building misc\\'
    "Debris / litter" = Group-Assets '(?i)\\misc\\debris\\'
}

Write-Host "BLACK SIGNAL - District 12 authored-kit audit"
Write-Host "List: $ListPath"
Write-Host "Cyberpunk Streets FPE references: $($pack.Count)"
Write-Host ""

foreach ($entry in $groups.GetEnumerator()) {
    Write-Host ("{0,-28} {1,4}" -f $entry.Key, $entry.Value.Count)
}

Write-Host ""
Write-Host "Core snap-building coverage"
$core = [ordered]@{
    "Straight road 4x" = 'cs_street_straight_4x\.fpe$'
    "Straight road 2x" = 'cs_street_straight_2x\.fpe$'
    "T intersection" = 'cs_street_t-intersect_3\.fpe$'
    "4-way intersection" = 'cs_street_4_way_2\.fpe$'
    "Road curve" = 'cs_street_curve_1\.fpe$'
    "Straight sidewalk edge" = 'cs_sidewalk_straight_edge\.fpe$'
    "Drop curb corner" = 'cs_sidewalk_corner1_dropcurb\.fpe$'
    "Wall" = 'cs_wall_01\.fpe$'
    "Wall corner" = 'cs_wall_corner_01\.fpe$'
    "Window wall" = 'cs_walls_01_window_with_bars\.fpe$'
    "Entry 01" = 'cs_wall_01_entry_01\.fpe$'
    "Entry 04" = 'cs_wall_01_entry_04\.fpe$'
    "Overhang" = 'cs_wall_01_overhang\.fpe$'
    "Overhang corner" = 'cs_wall_01_overhang_corner\.fpe$'
    "Roof 2x2" = 'cs_roof_tile_2x2\.fpe$'
    "Roof 4x4" = 'cs_roof_tile_4x4\.fpe$'
}

$missing = @()
foreach ($entry in $core.GetEnumerator()) {
    $found = @($pack | Where-Object { $_ -match $entry.Value }).Count -gt 0
    if ($found) { Write-Host "  [PASS] $($entry.Key)" }
    else { Write-Host "  [MISS] $($entry.Key)"; $missing += $entry.Key }
}

Write-Host ""
$background = $groups["Background buildings"]
if ($background.Count -gt 0) {
    Write-Host "Background skyline assets are referenced ($($background.Count))."
    Write-Host "Keep these outside the playable/hero street wall; they are skyline/perimeter mass."
}

$jungle = @($lines | Where-Object { $_ -match '(?i)entitybank\\jungle collection\\trees\\' })
if ($jungle.Count -gt 0) {
    Write-Host "[WARN] Jungle Collection tree assets are still referenced ($($jungle.Count))."
    Write-Host "       Keep them outside the urban core or remove/occlude them in hero city views."
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[WARN] Missing core authored-kit coverage: $($missing -join ', ')"
    exit 2
}

Write-Host ""
Write-Host "[PASS] District 12 references the core snap-built road/pavement/building kit."
Write-Host "       This audit checks dependency coverage only; visually verify placement and snapping in GameGuru MAX."
exit 0
