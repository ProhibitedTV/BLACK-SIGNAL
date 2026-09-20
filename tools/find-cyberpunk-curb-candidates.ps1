param(
    [string]$PackRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PackRoot)) {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Steam\steamapps\common\GameGuru MAX\Files\entitybank\cyberpunk streets booster pack"),
        (Join-Path $env:ProgramFiles "Steam\steamapps\common\GameGuru MAX\Files\entitybank\cyberpunk streets booster pack")
    )
    $PackRoot = $candidates | Where-Object { Test-Path -LiteralPath $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($PackRoot) -or -not (Test-Path -LiteralPath $PackRoot)) {
    throw @"
Cyberpunk Streets pack not found in the standard Steam location.
Pass the exact pack path reported by audit-cyberpunk-detail-assets.ps1, for example:
  powershell -ExecutionPolicy Bypass -File .\tools\find-cyberpunk-curb-candidates.ps1 -PackRoot "C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX\Files\entitybank\cyberpunk streets booster pack"
"@
}

$PackRoot = (Resolve-Path -LiteralPath $PackRoot).Path
$regex = '(?i)(parking|bollard|barrier|rail|railing|guard|fence|post|pole|curb|kerb|street.?furniture|sidewalk)'
$files = @(Get-ChildItem -LiteralPath $PackRoot -Filter '*.fpe' -File -Recurse | Where-Object {
    $_.BaseName -match $regex -or $_.DirectoryName -match $regex
} | Sort-Object FullName)

Write-Host "BLACK SIGNAL Cyberpunk curb-protection candidate scan"
Write-Host "Pack: $PackRoot"
Write-Host ""

if ($files.Count -eq 0) {
    Write-Host "No broad curb-protection candidates found."
    exit 0
}

foreach ($file in $files) {
    $relative = $file.FullName.Substring($PackRoot.Length).TrimStart('\')
    Write-Host $relative
}

Write-Host ""
Write-Host "Candidate count: $($files.Count)"
Write-Host "Choose by visual purpose, not filename alone. We want pieces that can form curb rails, bollard/post runs, parking separators, or pedestrian protection without blocking the roadway."
