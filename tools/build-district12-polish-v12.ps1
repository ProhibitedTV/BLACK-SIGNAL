param(
    [string]$Candidate,
    [switch]$Deploy,
    [string]$PythonPath = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$GameGuruInstall = 'C:\Program Files (x86)\Steam\steamapps\common\GameGuru MAX',
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files"
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source=Join-Path $repo 'gameguru\references\District 12 - manual polish.fpm'
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$name='BLACK SIGNAL - District 12'
if ($Deploy -and (Get-Process GameGuruMAX -ErrorAction SilentlyContinue)) { throw 'Save and close GameGuru MAX before applying the level.' }
& $PythonPath -B (Join-Path $PSScriptRoot 'prepare-polish-dependencies.py') --install $GameGuruInstall --output (Join-Path $repo 'gameguru\buildplans\city-polish-deps.lst')
if ($LASTEXITCODE -ne 0) { throw 'Installed asset dependency check failed.' }
if (-not $Candidate) {
    $Candidate=Join-Path $repo "_fpm_generated\$name-polish-v12-$stamp.fpm"
    & $PythonPath -B (Join-Path $PSScriptRoot 'fpm_polish_city_v12.py') --source $source --output $Candidate
    if ($LASTEXITCODE -ne 0) { throw 'Incremental export failed.' }
}
$Candidate=(Resolve-Path -LiteralPath $Candidate).Path
$receipt=Join-Path $repo "_fpm_generated\polish-v12-validation-$stamp.json"
& $PythonPath -B (Join-Path $PSScriptRoot 'fpm_validate_polish_v12.py') $Candidate --source $source --report $receipt
if ($LASTEXITCODE -ne 0) { throw 'Incremental export validation failed.' }
if (-not $Deploy) { Write-Host "Validated candidate: $Candidate"; return }
$sourceHash=(Get-FileHash -LiteralPath $source).Hash
$runtime=Join-Path $repo "Files\mapbank\$name.fpm"
$allowed=@($sourceHash)
$previous=Join-Path $repo 'gameguru\buildplans\district12-v12-validation.json'
if (Test-Path -LiteralPath $previous) { $allowed+=((Get-Content -LiteralPath $previous -Raw | ConvertFrom-Json).sha256) }
if ((Test-Path -LiteralPath $runtime) -and ((Get-FileHash -LiteralPath $runtime).Hash -notin $allowed)) { throw 'Project level has newer manual edits. Capture and review them before deployment.' }
$backup=Join-Path $repo "_fpm_backups\polish-v12-$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$targets=@(
    @{Map=(Join-Path $repo 'gameguru\maps');Files=(Join-Path $repo 'gameguru\Files');Label='curated'},
    @{Map=(Join-Path $repo 'Files\mapbank');Files=(Join-Path $repo 'Files');Label='project'},
    @{Map=(Join-Path $GameGuruFiles 'mapbank');Files=$GameGuruFiles;Label='global'}
)
foreach ($t in $targets) {
    foreach ($ext in @('fpm','lst')) {
        $f=Join-Path $t.Map "$name.$ext"
        if (Test-Path -LiteralPath $f) { Copy-Item -LiteralPath $f -Destination (Join-Path $backup ($t.Label+'.'+$ext)) }
    }
    foreach ($script in @('bs_city_extra.lua','bs_city_extra_routes.lua')) {
        $f=Join-Path $t.Files "scriptbank\user\black_signal\$script"
        if (Test-Path -LiteralPath $f) { Copy-Item -LiteralPath $f -Destination (Join-Path $backup ($t.Label+'-'+$script)) }
    }
}
$deps=@(Get-Content -LiteralPath (Join-Path $repo "gameguru\maps\$name.lst"))
foreach ($f in @('gameguru\references\District 12 - manual polish.lst','gameguru\buildplans\city-extra-deps.lst','gameguru\buildplans\city-polish-deps.lst','gameguru\buildplans\cybercity-dressing-deps-v11.lst')) { $deps+=Get-Content -LiteralPath (Join-Path $repo $f) }
$deps=@($deps | Where-Object { $_.Trim() } | Sort-Object -Unique)
$routes=[IO.Path]::ChangeExtension($Candidate,'.routes.lua')
$behavior=Join-Path $repo 'gameguru\Files\scriptbank\user\black_signal\bs_city_extra.lua'
$hash=(Get-FileHash -LiteralPath $Candidate).Hash
foreach ($t in $targets) {
    $dir=Join-Path $t.Files 'scriptbank\user\black_signal'
    New-Item -ItemType Directory -Force -Path $dir,$t.Map | Out-Null
    if ($t.Label -ne 'curated') { Copy-Item -LiteralPath $behavior -Destination (Join-Path $dir 'bs_city_extra.lua') -Force }
    Copy-Item -LiteralPath $routes -Destination (Join-Path $dir 'bs_city_extra_routes.lua') -Force
    Copy-Item -LiteralPath $Candidate -Destination (Join-Path $t.Map "$name.fpm") -Force
    [IO.File]::WriteAllLines((Join-Path $t.Map "$name.lst"),$deps,(New-Object Text.UTF8Encoding($false)))
    if ((Get-FileHash -LiteralPath (Join-Path $t.Map "$name.fpm")).Hash -ne $hash) { throw 'Map deployment hash mismatch.' }
    if ((Get-FileHash -LiteralPath (Join-Path $dir 'bs_city_extra_routes.lua')).Hash -ne (Get-FileHash -LiteralPath $routes).Hash) { throw 'Route deployment hash mismatch.' }
}
Copy-Item -LiteralPath $receipt -Destination $previous -Force
Copy-Item -LiteralPath ([IO.Path]::ChangeExtension($Candidate,'.report.json')) -Destination (Join-Path $repo 'gameguru\buildplans\district12-v12-layout.json') -Force
Write-Host "Applied incremental polish and pedestrians. SHA256: $hash"
Write-Host "Backup: $backup"
