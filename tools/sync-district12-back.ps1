param(
    [ValidateSet('Auto','Project','Global')]
    [string]$Source = 'Auto',
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mapName = 'BLACK SIGNAL - District 12.fpm'
$listName = 'BLACK SIGNAL - District 12.lst'
$dstDir = Join-Path $repo 'gameguru\maps'
$dstFpm = Join-Path $dstDir $mapName
$dstLst = Join-Path $dstDir $listName

$projectMapbank = Join-Path $repo 'Files\mapbank'
$globalMapbank = Join-Path $GameGuruFiles 'mapbank'

function New-Candidate([string]$Kind, [string]$Mapbank) {
    $fpm = Join-Path $Mapbank $mapName
    $lst = Join-Path $Mapbank $listName
    if (-not (Test-Path $fpm)) { return $null }
    $info = Get-Item $fpm
    [pscustomobject]@{
        Kind = $Kind
        Mapbank = $Mapbank
        Fpm = $fpm
        Lst = $lst
        LastWriteTimeUtc = $info.LastWriteTimeUtc
        Size = $info.Length
    }
}

$candidates = @()
$projectCandidate = New-Candidate -Kind 'Project' -Mapbank $projectMapbank
$globalCandidate = New-Candidate -Kind 'Global' -Mapbank $globalMapbank
if ($null -ne $projectCandidate) { $candidates += $projectCandidate }
if ($null -ne $globalCandidate) { $candidates += $globalCandidate }

if ($candidates.Count -eq 0) {
    throw "District 12 was not found in either mapbank:`n  Project: $projectMapbank`n  Global:  $globalMapbank"
}

switch ($Source) {
    'Project' {
        if ($null -eq $projectCandidate) { throw "Project-local District 12 map was not found: $projectMapbank" }
        $selected = $projectCandidate
    }
    'Global' {
        if ($null -eq $globalCandidate) { throw "Global District 12 map was not found: $globalMapbank" }
        $selected = $globalCandidate
    }
    default {
        $selected = $candidates | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    }
}

Write-Host 'BLACK SIGNAL - sync District 12 back to curated source'
Write-Host "Repo: $repo"
Write-Host ''
Write-Host 'Detected map copies:'
foreach ($candidate in ($candidates | Sort-Object Kind)) {
    Write-Host ("  {0,-7} {1:u}  {2:N2} MiB  {3}" -f $candidate.Kind, $candidate.LastWriteTimeUtc, ($candidate.Size / 1MB), $candidate.Fpm)
}
Write-Host ''
Write-Host ("Selected {0} map ({1} mode):" -f $selected.Kind, $Source)
Write-Host "  $($selected.Fpm)"
Write-Host ''

New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
Copy-Item -Force $selected.Fpm $dstFpm
if (Test-Path $selected.Lst) {
    Copy-Item -Force $selected.Lst $dstLst
}

& git -C $repo add -- 'gameguru/maps/BLACK SIGNAL - District 12.fpm'
if (Test-Path $dstLst) {
    & git -C $repo add -- 'gameguru/maps/BLACK SIGNAL - District 12.lst'
}
if ($LASTEXITCODE -ne 0) { throw 'git add failed while staging District 12.' }

Write-Host 'District 12 synced back from GameGuru MAX.'
Write-Host ''

& git -C $repo diff --cached --quiet -- 'gameguru/maps/BLACK SIGNAL - District 12.fpm' 'gameguru/maps/BLACK SIGNAL - District 12.lst'
if ($LASTEXITCODE -eq 0) {
    Write-Host 'No District 12 map changes were detected.'
    Write-Host ("The selected source was the {0} mapbank copy above." -f $selected.Kind)
    Write-Host 'If you just edited Block 01, make sure the level itself was saved in MAX, not only the Storyboard/project.'
    exit 0
}

Write-Host 'Staged District 12 changes:'
& git -C $repo status --short -- 'gameguru/maps/BLACK SIGNAL - District 12.fpm' 'gameguru/maps/BLACK SIGNAL - District 12.lst'
Write-Host ''
Write-Host 'Review the staged map before committing.'
Write-Host 'Suggested commit:'
Write-Host '  git commit -m "Author District 12 Block 01 hero junction"'
Write-Host '  git push'
