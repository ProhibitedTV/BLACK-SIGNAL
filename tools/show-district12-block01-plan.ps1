param(
    [string]$PlanPath,
    [string]$ListPath
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($PlanPath)) {
    $PlanPath = Join-Path $repo "gameguru\buildplans\district12\block-01-hero-junction.csv"
}
if ([string]::IsNullOrWhiteSpace($ListPath)) {
    $ListPath = Join-Path $repo "gameguru\maps\BLACK SIGNAL - District 12.lst"
}

if (-not (Test-Path $PlanPath)) { throw "Block 01 build plan not found: $PlanPath" }
if (-not (Test-Path $ListPath)) { throw "District 12 dependency list not found: $ListPath" }

function Normalize-AssetName([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { return "" }
    return (($Name.ToLowerInvariant() -replace '\.fpe$','') -replace '[^a-z0-9]','')
}

$listText = Get-Content -Raw -Path $ListPath
$loadedAssets = New-Object 'System.Collections.Generic.HashSet[string]'
$matches = [regex]::Matches($listText, '(?i)(?:^|[\\/])([^\\/\r\n]+\.fpe)')
foreach ($match in $matches) {
    [void]$loadedAssets.Add((Normalize-AssetName $match.Groups[1].Value))
}

$rows = @(Import-Csv -Path $PlanPath)
if ($rows.Count -eq 0) { throw "Block 01 build plan is empty: $PlanPath" }

Write-Host "BLACK SIGNAL — District 12 Block 01 build checklist"
Write-Host "Plan: $PlanPath"
Write-Host "Level dependency list: $ListPath"
Write-Host ""

$requiredMissing = 0
$optionalMissing = 0
$ready = 0
$currentPhase = $null
$currentZone = $null

foreach ($row in $rows) {
    if ($row.phase -ne $currentPhase) {
        $currentPhase = $row.phase
        $currentZone = $null
        Write-Host ""
        Write-Host "=== PHASE $currentPhase ==="
    }
    if ($row.zone -ne $currentZone) {
        $currentZone = $row.zone
        Write-Host ""
        Write-Host "[$currentZone]"
    }

    $normalized = Normalize-AssetName $row.asset
    $present = $loadedAssets.Contains($normalized)
    $required = ($row.required -match '^(?i:yes|true|1)$')

    if ($present) {
        $ready++
        $state = "READY"
    } elseif ($required) {
        $requiredMissing++
        $state = "MISSING REQUIRED"
    } else {
        $optionalMissing++
        $state = "optional not loaded"
    }

    Write-Host ("  [{0}] {1}" -f $state, $row.asset)
    Write-Host ("       place: {0}" -f $row.placement_rule)
    Write-Host ("       rotate: {0}" -f $row.rotation_rule)
    if (-not [string]::IsNullOrWhiteSpace($row.notes)) {
        Write-Host ("       note: {0}" -f $row.notes)
    }
}

Write-Host ""
Write-Host "Summary"
Write-Host "  Ready in current District 12 list: $ready"
Write-Host "  Missing required plan assets: $requiredMissing"
Write-Host "  Missing optional detail assets: $optionalMissing"
Write-Host ""
Write-Host "Build contract: structural pieces stay at native scale, snap to the MAX grid, and use orthogonal rotations."
Write-Host "The saved FPM remains the physical-city source of truth; this tool does not generate or modify map geometry."

if ($requiredMissing -gt 0) {
    Write-Host ""
    Write-Host "Add the missing required assets through GameGuru MAX before completing Block 01."
    exit 1
}

exit 0
