param(
    [string]$ProjectFile,
    [string]$GameGuruFiles = "$env:USERPROFILE\Documents\GameGuruApps\GameGuruMAX\Files",
    [string]$ProjectFiles,
    [switch]$AllowGameGuruRunning
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# GameGuru MAX 2026 StoryboardStruct v203 layout. Keep these values in sync with
# tools/repair-black-signal-storyboard.ps1 and the public GameGuru MAX source.
$ExpectedVersion = 203
$ExpectedSize = 58930212L
$StoryboardHeaderSize = 284L
$NodeSize = 376416L
$NodeCount = 150
$NodeUsedOffset = 20L
$NodeTitleOffset = 28L
$NodeThumbOffset = 540L
$ScreenBackdropOffset = 33276L
$ScreenBackdropIdOffset = 33532L
$ScreenBackdropPlacementOffset = 33552L
$ScreenThumbOffset = 33556L
$ScreenRatioPlacementOffset = 33812L
$ScreenBackdropTransparentOffset = 220256L
$CStringLength = 256
$BackdropPlacementZoom = 2

if ([string]::IsNullOrWhiteSpace($ProjectFile)) {
    $ProjectFile = Join-Path $repo "Files\projectbank\BLACK SIGNAL\project203.dat"
}
if ([string]::IsNullOrWhiteSpace($ProjectFiles)) {
    $ProjectFiles = Join-Path $repo "Files"
}

$ScreenMap = [ordered]@{
    "Splash Screen"            = "splash.jpg"
    "Title Screen"             = "title.jpg"
    "Loading Screen"           = "loading.jpg"
    "Game Paused"              = "pause.jpg"
    "Game Over Screen"         = "gameover.jpg"
    "Game Won Screen"          = "win.jpg"
    "Save Game Screen"         = "submenu.jpg"
    "Load Game Screen"         = "submenu.jpg"
    "Graphics Settings Screen" = "submenu.jpg"
    "Sound Settings Screen"    = "submenu.jpg"
    "Controls Screen"          = "submenu.jpg"
    "About Screen"             = "submenu.jpg"
}
$CriticalScreens = @("Splash Screen", "Title Screen", "Loading Screen", "Game Paused", "Game Over Screen")

function New-Brush([int]$R, [int]$G, [int]$B, [int]$A = 255) {
    return New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb($A, $R, $G, $B))
}

function New-Pen([int]$R, [int]$G, [int]$B, [int]$A, [float]$Width) {
    return New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb($A, $R, $G, $B)), $Width
}

function Draw-CornerBracket($Graphics, [System.Drawing.Pen]$Pen, [int]$X, [int]$Y, [int]$DX, [int]$DY) {
    $Graphics.DrawLine($Pen, $X, $Y, $X + (28 * $DX), $Y)
    $Graphics.DrawLine($Pen, $X, $Y, $X, $Y + (28 * $DY))
}

function Draw-CenteredText($Graphics, [string]$Text, [System.Drawing.Font]$Font, [System.Drawing.Brush]$Brush, [float]$Y, [float]$Width = 1920) {
    $format = New-Object System.Drawing.StringFormat
    try {
        $format.Alignment = [System.Drawing.StringAlignment]::Center
        $format.LineAlignment = [System.Drawing.StringAlignment]::Near
        $Graphics.DrawString($Text, $Font, $Brush, (New-Object System.Drawing.RectangleF 0, $Y, $Width, 180), $format)
    }
    finally {
        $format.Dispose()
    }
}

function New-BlackSignalScreen([string]$Path, [string]$Kind) {
    $width = 1920
    $height = 1080
    $bmp = New-Object System.Drawing.Bitmap $width, $height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    $fontTitle = New-Object System.Drawing.Font "Consolas", 82, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $fontHeader = New-Object System.Drawing.Font "Consolas", 38, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
    $fontSmall = New-Object System.Drawing.Font "Consolas", 18, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
    $fontTiny = New-Object System.Drawing.Font "Consolas", 14, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)

    $white = New-Brush 222 239 246 255
    $cyan = New-Brush 142 219 242 255
    $muted = New-Brush 135 164 177 230
    $panelBrush = New-Brush 2 9 14 165
    $panelEdge = New-Pen 128 218 242 125 2
    $edgePen = New-Pen 172 225 242 190 2
    $signalPen = New-Pen 103 195 224 105 1
    $planetPen = New-Pen 110 184 211 95 4
    $planetGlow = New-Pen 110 184 211 34 22

    try {
        # Deep-space gradient.
        $rect = New-Object System.Drawing.Rectangle 0, 0, $width, $height
        $gradient = New-Object System.Drawing.Drawing2D.LinearGradientBrush $rect, ([System.Drawing.Color]::FromArgb(255, 2, 6, 10)), ([System.Drawing.Color]::FromArgb(255, 10, 22, 31)), 28.0
        try { $g.FillRectangle($gradient, $rect) } finally { $gradient.Dispose() }

        # Deterministic star/noise field so every build is byte-stable enough visually.
        $rng = New-Object System.Random 1420405
        for ($i = 0; $i -lt 360; $i++) {
            $x = $rng.Next(18, $width - 18)
            $y = $rng.Next(18, $height - 18)
            $r = if (($i % 29) -eq 0) { 3 } elseif (($i % 7) -eq 0) { 2 } else { 1 }
            $a = $rng.Next(35, 160)
            $star = New-Brush 198 227 239 $a
            try { $g.FillEllipse($star, $x, $y, $r, $r) } finally { $star.Dispose() }
        }

        # Cold planet / receiver-horizon motif on the right.
        $planetRect = New-Object System.Drawing.RectangleF 1280, -170, 810, 810
        $g.DrawEllipse($planetGlow, $planetRect)
        $g.DrawEllipse($planetPen, $planetRect)
        for ($i = 0; $i -lt 5; $i++) {
            $arcPen = New-Pen 132 204 226 (35 - ($i * 4)) 1
            try { $g.DrawArc($arcPen, 1310 + ($i * 8), -140 + ($i * 8), 750 - ($i * 16), 750 - ($i * 16), 115, 120) } finally { $arcPen.Dispose() }
        }

        # Subtle scanlines and signal traces.
        for ($y = 0; $y -lt $height; $y += 7) {
            $scan = New-Pen 130 194 214 13 1
            try { $g.DrawLine($scan, 0, $y, $width, $y) } finally { $scan.Dispose() }
        }
        $g.DrawLine($signalPen, 46, 116, 620, 116)
        $g.DrawLine($signalPen, 1300, 116, 1874, 116)
        $g.DrawLine($signalPen, 88, 936, 500, 936)
        $g.DrawLine($signalPen, 1420, 936, 1832, 936)

        Draw-CornerBracket $g $edgePen 28 28 1 1
        Draw-CornerBracket $g $edgePen ($width - 28) 28 -1 1
        Draw-CornerBracket $g $edgePen 28 ($height - 28) 1 -1
        Draw-CornerBracket $g $edgePen ($width - 28) ($height - 28) -1 -1

        $g.DrawString("SIGNAL: UNKNOWN`nFREQ: 1420.405 MHz`nSTATUS: DETECTED", $fontTiny, $muted, 52, 48)
        $g.DrawString("BLACK SIGNAL  v1.0`nGAMEGURU MAX PROJECT", $fontTiny, $muted, 52, 980)
        $g.DrawString("SOME SIGNALS`nSHOULD STAY`nSILENT", $fontTiny, $muted, 1690, 48)
        $g.DrawString("WE LISTEN ANYWAY", $fontTiny, $muted, 1665, 1000)

        $titleY = if ($Kind -eq "splash") { 365 } else { 125 }
        Draw-CenteredText $g "BLACK SIGNAL" $fontTitle $white $titleY

        switch ($Kind) {
            "splash" {
                Draw-CenteredText $g "SOME THINGS ARE STILL LISTENING" $fontHeader $cyan 485
                Draw-CenteredText $g "A SCIENCE-FICTION THRILLER EXPERIENCE" $fontSmall $muted 565
                $g.FillRectangle($panelBrush, 700, 790, 520, 74)
                $g.DrawRectangle($panelEdge, 700, 790, 520, 74)
                Draw-CenteredText $g "PRESS ANY KEY TO CONTINUE" $fontSmall $white 813
            }
            "title" {
                Draw-CenteredText $g "SOME THINGS ARE STILL LISTENING" $fontSmall $muted 245
                $g.FillRectangle($panelBrush, 610, 330, 700, 560)
                $g.DrawRectangle($panelEdge, 610, 330, 700, 560)
                $g.DrawString("DISTANT WORLDS`nDISTORTED SIGNALS`nUNANSWERED QUESTIONS`nSAME SKY", $fontTiny, $muted, 54, 600)
            }
            "loading" {
                Draw-CenteredText $g "ESTABLISHING UPLINK" $fontHeader $cyan 725
                Draw-CenteredText $g "SYNCHRONIZING SIGNAL // DECRYPTING LEVEL DATA" $fontSmall $muted 792
                $g.FillRectangle($panelBrush, 440, 875, 1040, 34)
                $g.DrawRectangle($panelEdge, 440, 875, 1040, 34)
                $g.FillRectangle($cyan, 452, 887, 360, 10)
            }
            "pause" {
                Draw-CenteredText $g "GAME PAUSED" $fontHeader $cyan 245
                $g.FillRectangle($panelBrush, 610, 330, 700, 560)
                $g.DrawRectangle($panelEdge, 610, 330, 700, 560)
            }
            "gameover" {
                Draw-CenteredText $g "SIGNAL LOST // GAME OVER" $fontHeader $cyan 245
                $g.FillRectangle($panelBrush, 610, 365, 700, 430)
                $g.DrawRectangle($panelEdge, 610, 365, 700, 430)
            }
            "win" {
                Draw-CenteredText $g "SIGNAL RESTORED" $fontHeader $cyan 245
                $g.FillRectangle($panelBrush, 610, 365, 700, 430)
                $g.DrawRectangle($panelEdge, 610, 365, 700, 430)
            }
            default {
                Draw-CenteredText $g "SIGNAL INTERFACE" $fontSmall $muted 245
                $g.FillRectangle($panelBrush, 520, 300, 880, 640)
                $g.DrawRectangle($panelEdge, 520, 300, 880, 640)
            }
        }

        $dir = Split-Path -Parent $Path
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    }
    finally {
        foreach ($obj in @($planetGlow, $planetPen, $signalPen, $edgePen, $panelEdge, $panelBrush, $muted, $cyan, $white, $fontTiny, $fontSmall, $fontHeader, $fontTitle, $g, $bmp)) {
            if ($null -ne $obj) { $obj.Dispose() }
        }
    }
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
    if ($bytes.Length -ge $Length) { throw "Storyboard string is too long: $Value" }
    $buffer = New-Object byte[] $Length
    [Array]::Copy($bytes, $buffer, $bytes.Length)
    $Writer.BaseStream.Position = $Offset
    $Writer.Write($buffer)
}

function Write-Int32At([System.IO.BinaryWriter]$Writer, [long]$Offset, [int]$Value) {
    $Writer.BaseStream.Position = $Offset
    $Writer.Write([int]$Value)
}

Write-Host "BLACK SIGNAL - install Storyboard UI"
Write-Host "Project: $ProjectFile"
Write-Host ""

if (-not $AllowGameGuruRunning) {
    $running = @(Get-Process -Name "GameGuruMAX" -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) {
        throw "GameGuru MAX is running. Close MAX first so its in-memory Storyboard cannot overwrite the BLACK SIGNAL UI changes."
    }
}

if (-not (Test-Path $ProjectFile)) { throw "BLACK SIGNAL storyboard not found: $ProjectFile" }
$info = Get-Item $ProjectFile
if ($info.Length -ne $ExpectedSize) {
    throw "Unexpected project203.dat size: $($info.Length) bytes. Expected $ExpectedSize for Storyboard v203."
}

try { Add-Type -AssemblyName System.Drawing } catch { throw "System.Drawing is required to build BLACK SIGNAL Storyboard artwork: $($_.Exception.Message)" }

$generatedRoot = Join-Path $repo ".black-signal\generated-ui\1920x1080"
$screenKinds = [ordered]@{
    "splash.jpg"   = "splash"
    "title.jpg"    = "title"
    "loading.jpg"  = "loading"
    "pause.jpg"    = "pause"
    "gameover.jpg" = "gameover"
    "win.jpg"      = "win"
    "submenu.jpg"  = "submenu"
}
foreach ($entry in $screenKinds.GetEnumerator()) {
    $output = Join-Path $generatedRoot $entry.Key
    New-BlackSignalScreen -Path $output -Kind $entry.Value
    Write-Host "[BUILT] $($entry.Key)"
}

$destinations = @(
    (Join-Path $ProjectFiles "titlesbank\black_signal\1920x1080"),
    (Join-Path $GameGuruFiles "titlesbank\black_signal\1920x1080")
) | Select-Object -Unique
foreach ($dest in $destinations) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($entry in $screenKinds.GetEnumerator()) {
        Copy-Item -Force (Join-Path $generatedRoot $entry.Key) (Join-Path $dest $entry.Key)
    }
    Write-Host "[INSTALLED] UI artwork -> $dest"
}

$stream = [System.IO.File]::Open($ProjectFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
$reader = New-Object System.IO.BinaryReader($stream, [System.Text.Encoding]::ASCII, $true)
$nodes = @()
try {
    $signature = Read-CStringAt $reader 0 12
    if ($signature -ne "Storyboard") { throw "Invalid storyboard signature '$signature'." }
    $version = Read-Int32At $reader 268
    if ($version -ne $ExpectedVersion) { throw "Unexpected Storyboard version $version; expected $ExpectedVersion." }

    for ($i = 0; $i -lt $NodeCount; $i++) {
        $base = $StoryboardHeaderSize + ($i * $NodeSize)
        if ((Read-Int32At $reader ($base + $NodeUsedOffset)) -eq 0) { continue }
        $title = Read-CStringAt $reader ($base + $NodeTitleOffset) $CStringLength
        if ($ScreenMap.Contains($title)) {
            $current = Read-CStringAt $reader ($base + $ScreenBackdropOffset) $CStringLength
            $nodes += [pscustomobject]@{ Index = $i; Base = $base; Title = $title; Current = $current; File = $ScreenMap[$title] }
        }
    }
}
finally {
    $reader.Dispose()
    $stream.Dispose()
}

foreach ($critical in $CriticalScreens) {
    if (@($nodes | Where-Object { $_.Title -ieq $critical }).Count -eq 0) {
        throw "Required Storyboard node '$critical' was not found. Refusing to partially theme the project."
    }
}

$needsPatch = $false
foreach ($node in $nodes) {
    $wanted = "titlesbank\black_signal\1920x1080\$($node.File)"
    if ($node.Current -ine $wanted) { $needsPatch = $true; break }
}

if ($needsPatch) {
    $backupRoot = Join-Path $repo ".black-signal\backups\storyboard-ui"
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $backup = Join-Path $backupRoot "project203_$stamp.dat"
    Copy-Item -Force $ProjectFile $backup
    Write-Host "Backed up Storyboard to: $backup"

    $stream = [System.IO.File]::Open($ProjectFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
    $writer = New-Object System.IO.BinaryWriter($stream, [System.Text.Encoding]::ASCII, $true)
    try {
        foreach ($node in $nodes) {
            $relative = "titlesbank\black_signal\1920x1080\$($node.File)"
            Write-CStringAt $writer ($node.Base + $ScreenBackdropOffset) $CStringLength $relative
            Write-Int32At $writer ($node.Base + $ScreenBackdropIdOffset) 0
            Write-Int32At $writer ($node.Base + $ScreenBackdropPlacementOffset) $BackdropPlacementZoom
            Write-CStringAt $writer ($node.Base + $ScreenThumbOffset) $CStringLength $relative
            Write-CStringAt $writer ($node.Base + $NodeThumbOffset) $CStringLength $relative
            Write-Int32At $writer ($node.Base + $ScreenBackdropTransparentOffset) 0
            for ($r = 0; $r -lt 10; $r++) {
                Write-Int32At $writer ($node.Base + $ScreenRatioPlacementOffset + ($r * 4)) $BackdropPlacementZoom
            }
            Write-Host "[THEMED] node $($node.Index): $($node.Title) -> $relative"
        }
        $writer.Flush()
        $stream.Flush()
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
} else {
    Write-Host "[PASS] Storyboard already points at BLACK SIGNAL UI artwork."
}

# Fresh verification read: every target node must point at an installed asset.
$verifyStream = [System.IO.File]::OpenRead($ProjectFile)
$verifyReader = New-Object System.IO.BinaryReader($verifyStream, [System.Text.Encoding]::ASCII, $true)
try {
    foreach ($node in $nodes) {
        $relative = "titlesbank\black_signal\1920x1080\$($node.File)"
        $actual = Read-CStringAt $verifyReader ($node.Base + $ScreenBackdropOffset) $CStringLength
        if ($actual -ine $relative) { throw "Storyboard UI verification failed for '$($node.Title)': '$actual'" }
        foreach ($root in @($ProjectFiles, $GameGuruFiles) | Select-Object -Unique) {
            $asset = Join-Path $root $relative
            if (-not (Test-Path $asset)) { throw "Storyboard UI asset is missing after install: $asset" }
        }
    }
}
finally {
    $verifyReader.Dispose()
    $verifyStream.Dispose()
}

Write-Host ""
Write-Host "[PASS] BLACK SIGNAL Storyboard UI is installed."
Write-Host "       Splash, title, loading, pause and game-over screens have dedicated artwork."
Write-Host "       Save/load/settings/controls/about screens share the BLACK SIGNAL submenu treatment."
Write-Host "       Existing Storyboard widgets/actions remain intact and interactive above the themed backdrops."
