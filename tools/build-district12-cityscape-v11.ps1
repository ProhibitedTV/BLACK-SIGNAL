param(
    [string]$PythonPath,
    [string]$Candidate,
    [switch]$Deploy,
    [string]$GameGuruInstall = 'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX',
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Deploy -and (Get-Process GameGuruMAX -ErrorAction SilentlyContinue)) {
    throw 'Save and close GameGuru MAX before deployment so its open state cannot overwrite the new city.'
}
if (-not $PythonPath) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $PythonPath = $bundled }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) { $PythonPath = $pythonCommand.Source }
        else { throw 'Pass -PythonPath with a working Python 3 executable.' }
    }
}
$reference = Join-Path $repo 'gameguru\references\District 12 - human corner.fpm'
$measurements = Join-Path $repo 'docs\cybercity-kit-measurements.json'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$generated = Join-Path $repo '_fpm_generated'
New-Item -ItemType Directory -Force -Path $generated | Out-Null
& $PythonPath -B (Join-Path $PSScriptRoot 'measure-cybercity-kit.py') --install $GameGuruInstall --scratch (Join-Path $generated 'mesh-audit-v11') --output $measurements
if ($LASTEXITCODE -ne 0) { throw 'Live mesh measurement failed.' }
if (-not $Candidate) {
    $Candidate = Join-Path $generated "BLACK SIGNAL - District 12 - populated-v11-$stamp.fpm"
    & $PythonPath -B (Join-Path $PSScriptRoot 'fpm_author_cityscape_v11.py') --reference $reference --output $Candidate --measurements $measurements
    if ($LASTEXITCODE -ne 0) { throw 'City export failed; deployment stopped.' }
}
$Candidate = (Resolve-Path -LiteralPath $Candidate).Path
$validation = Join-Path $generated "populated-v11-validation-$stamp.json"
& $PythonPath -B (Join-Path $PSScriptRoot 'fpm_validate_cityscape_v11.py') $Candidate --reference $reference --measurements $measurements --report $validation
if ($LASTEXITCODE -ne 0) { throw 'Saved city verification failed; deployment stopped.' }
if (-not $Deploy) { Write-Host "Validated candidate: $Candidate"; return }
$backup = Join-Path $repo "_fpm_backups\cityscape-v11-$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$name = 'BLACK SIGNAL - District 12'
$targets = @(
    @{ Root = (Join-Path $repo 'gameguru\maps'); Label = 'curated' },
    @{ Root = (Join-Path $repo 'Files\mapbank'); Label = 'project' },
    @{ Root = (Join-Path $GameGuruFiles 'mapbank'); Label = 'global' }
)
# Back up every target before changing any map.
foreach ($target in $targets) {
    foreach ($extension in @('fpm','lst')) {
        $existing = Join-Path $target.Root "$name.$extension"
        if (Test-Path -LiteralPath $existing) {
            Copy-Item -LiteralPath $existing -Destination (Join-Path $backup ($target.Label + '.' + $extension))
        }
    }
}
$dependencies = @(Get-Content -LiteralPath (Join-Path $repo "gameguru\maps\$name.lst"))
$dependencies += @(Get-Content -LiteralPath (Join-Path $repo 'gameguru\buildplans\district12-v10-5-human-street-deps.lst'))
$dependencies += @(Get-Content -LiteralPath (Join-Path $repo 'gameguru\buildplans\cybercity-dressing-deps-v11.lst'))
$dependencies = @($dependencies | Where-Object { $_.Trim() } | Sort-Object -Unique)
$hash = (Get-FileHash -LiteralPath $Candidate -Algorithm SHA256).Hash
foreach ($target in $targets) {
    New-Item -ItemType Directory -Force -Path $target.Root | Out-Null
    $map = Join-Path $target.Root "$name.fpm"
    Copy-Item -LiteralPath $Candidate -Destination $map -Force
    [IO.File]::WriteAllLines((Join-Path $target.Root "$name.lst"),$dependencies,(New-Object Text.UTF8Encoding($false)))
    if ((Get-FileHash -LiteralPath $map -Algorithm SHA256).Hash -ne $hash) { throw "Deployment hash mismatch: $map" }
}
$plans = Join-Path $repo 'gameguru\buildplans'
Copy-Item -LiteralPath $validation -Destination (Join-Path $plans 'district12-v11-validation.json') -Force
$layoutReport = [IO.Path]::ChangeExtension($Candidate,'.report.json')
if (Test-Path -LiteralPath $layoutReport) {
    Copy-Item -LiteralPath $layoutReport -Destination (Join-Path $plans 'district12-v11-layout.json') -Force
}
Write-Host "Applied verified city to curated, project and global maps. SHA256: $hash"
Write-Host "Backups: $backup"
Write-Host 'Native visual review remains a separate acceptance step.'
