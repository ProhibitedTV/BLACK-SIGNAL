param(
    [string]$ProjectFile,
    [string]$LevelName = "mapbank\BLACK SIGNAL - District 12.fpm",
    [switch]$AllowGameGuruRunning
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# GameGuru MAX 2026 storyboard format, verified against the public GameGuruMAX
# source for STORYBOARDVERSION 203. project203.dat is a raw StoryboardStruct.
$ExpectedVersion = 203
$ExpectedSize = 58930212L
$StoryboardHeaderSize = 284L
$NodeSize = 376416L
$NodeCount = 150
$NodeTypeOffset = 0L
$NodeUsedOffset = 20L
$NodeTitleOffset = 28L
$NodeLevelNameOffset = 796L
$CStringLength = 256
$LevelNodeType = 3

if ([string]::IsNullOrWhiteSpace($ProjectFile)) {
    $ProjectFile = Join-Path $repo "Files\projectbank\BLACK SIGNAL\project203.dat"
}

function Read-Int32At([System.IO.BinaryReader]$Reader, [long]$Offset) {
    $Reader.BaseStream.Position = $Offset
    return $Reader.ReadInt32()
}

function Read-CStringAt([System.IO.BinaryReader]$Reader, [long]$Offset, [int]$Length) {
    $Reader.BaseStream.Position = $Offset
    $bytes = $Reader.ReadBytes($Length)
    $end = [Array]::IndexOf($bytes, [byte]0)
    if ($end -lt 0) { $end = $bytes.Length }
    if ($end -eq 0) { return "" }
    return [System.Text.Encoding]::ASCII.GetString($bytes, 0, $end)
}

function Write-CStringAt([System.IO.BinaryWriter]$Writer, [long]$Offset, [int]$Length, [string]$Value) {
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($Value)
    if ($bytes.Length -ge $Length) {
        throw "Value is too long for a $Length-byte storyboard string: $Value"
    }
    $buffer = New-Object byte[] $Length
    [Array]::Copy($bytes, $buffer, $bytes.Length)
    $Writer.BaseStream.Position = $Offset
    $Writer.Write($buffer)
}

Write-Host "BLACK SIGNAL - Storyboard level repair"
Write-Host "Project: $ProjectFile"
Write-Host "Target:  $LevelName"
Write-Host ""

if (-not $AllowGameGuruRunning) {
    $running = @(Get-Process -Name "GameGuruMAX" -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) {
        throw "GameGuru MAX is running. Close MAX first so it cannot overwrite project203.dat, then run this repair again."
    }
}

if (-not (Test-Path $ProjectFile)) {
    throw "BLACK SIGNAL storyboard was not found: $ProjectFile"
}

$info = Get-Item $ProjectFile
if ($info.Length -ne $ExpectedSize) {
    throw "Unexpected project203.dat size: $($info.Length) bytes. Expected $ExpectedSize bytes for STORYBOARDVERSION 203. Refusing to patch an unknown binary layout."
}

$stream = [System.IO.File]::Open($ProjectFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
$reader = New-Object System.IO.BinaryReader($stream, [System.Text.Encoding]::ASCII, $true)
$writer = New-Object System.IO.BinaryWriter($stream, [System.Text.Encoding]::ASCII, $true)

try {
    $signature = Read-CStringAt $reader 0 12
    if ($signature -ne "Storyboard") {
        throw "Invalid storyboard signature '$signature'. Refusing to patch."
    }

    $version = Read-Int32At $reader 268
    if ($version -ne $ExpectedVersion) {
        throw "Unexpected storyboard version $version. Expected $ExpectedVersion. Refusing to patch."
    }

    Write-Host "[PASS] Storyboard signature/version are valid (v$version)"

    $levelNodes = @()
    for ($i = 0; $i -lt $NodeCount; $i++) {
        $base = $StoryboardHeaderSize + ($i * $NodeSize)
        $type = Read-Int32At $reader ($base + $NodeTypeOffset)
        $used = Read-Int32At $reader ($base + $NodeUsedOffset)
        if ($used -ne 0 -and $type -eq $LevelNodeType) {
            $title = Read-CStringAt $reader ($base + $NodeTitleOffset) $CStringLength
            $level = Read-CStringAt $reader ($base + $NodeLevelNameOffset) $CStringLength
            $levelNodes += [pscustomobject]@{
                Index = $i
                Base = $base
                Title = $title
                LevelName = $level
            }
        }
    }

    if ($levelNodes.Count -eq 0) {
        throw "The Storyboard has no used LEVEL node. Refusing to invent graph topology; create/add a level node in MAX first."
    }

    Write-Host "Found $($levelNodes.Count) used Storyboard LEVEL node(s):"
    foreach ($node in $levelNodes) {
        $shown = if ([string]::IsNullOrWhiteSpace($node.LevelName)) { "<EMPTY>" } else { $node.LevelName }
        Write-Host "  node $($node.Index): '$($node.Title)' -> $shown"
    }

    $already = @($levelNodes | Where-Object { $_.LevelName -ieq $LevelName })
    if ($already.Count -gt 0) {
        Write-Host ""
        Write-Host "[PASS] District 12 is already attached to Storyboard node $($already[0].Index)."
        exit 0
    }

    $emptyNodes = @($levelNodes | Where-Object { [string]::IsNullOrWhiteSpace($_.LevelName) })
    if ($emptyNodes.Count -eq 0) {
        throw "No empty LEVEL placeholder exists. Existing level bindings were left untouched."
    }

    # The stock project creates a wired 'Level 1' placeholder. Prefer it when
    # available; otherwise use the only/first empty level node and preserve all
    # of its existing links, actions, title, and screen routing.
    $candidate = $emptyNodes | Where-Object { $_.Title -ieq "Level 1" } | Select-Object -First 1
    if (-not $candidate) {
        $candidate = $emptyNodes | Select-Object -First 1
    }

    $backupRoot = Join-Path $repo ".black-signal\backups\storyboard"
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $backup = Join-Path $backupRoot "project203_$stamp.dat"

    # Flush/close before making a byte-for-byte safety copy.
    $writer.Flush()
    $stream.Flush()
    $reader.Dispose()
    $writer.Dispose()
    $stream.Dispose()
    $reader = $null
    $writer = $null
    $stream = $null

    Copy-Item -Force $ProjectFile $backup
    Write-Host "Backed up Storyboard to: $backup"

    $stream = [System.IO.File]::Open($ProjectFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
    $writer = New-Object System.IO.BinaryWriter($stream, [System.Text.Encoding]::ASCII, $true)

    Write-CStringAt $writer ($candidate.Base + $NodeLevelNameOffset) $CStringLength $LevelName
    $writer.Flush()
    $stream.Flush()

    Write-Host "[FIXED] Storyboard node $($candidate.Index) ('$($candidate.Title)') now points to: $LevelName"
}
finally {
    if ($reader) { $reader.Dispose() }
    if ($writer) { $writer.Dispose() }
    if ($stream) { $stream.Dispose() }
}

# Verify with a fresh read so a partial write can never be reported as success.
$verifyStream = [System.IO.File]::OpenRead($ProjectFile)
$verifyReader = New-Object System.IO.BinaryReader($verifyStream, [System.Text.Encoding]::ASCII, $true)
try {
    $bound = $false
    for ($i = 0; $i -lt $NodeCount; $i++) {
        $base = $StoryboardHeaderSize + ($i * $NodeSize)
        $type = Read-Int32At $verifyReader ($base + $NodeTypeOffset)
        $used = Read-Int32At $verifyReader ($base + $NodeUsedOffset)
        if ($used -ne 0 -and $type -eq $LevelNodeType) {
            $level = Read-CStringAt $verifyReader ($base + $NodeLevelNameOffset) $CStringLength
            if ($level -ieq $LevelName) {
                Write-Host "[PASS] Verified Storyboard binding on node $i"
                $bound = $true
                break
            }
        }
    }
    if (-not $bound) {
        throw "Storyboard verification failed after patch. Restore the newest backup from .black-signal\backups\storyboard."
    }
}
finally {
    $verifyReader.Dispose()
    $verifyStream.Dispose()
}

Write-Host "Storyboard repair complete."
exit 0
