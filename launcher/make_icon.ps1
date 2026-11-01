# Draws the HealthyCoach leaf logo and writes assets\healthycoach.ico (16-256 px PNG entries).
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force (Join-Path $root "assets") | Out-Null
$icoPath = Join-Path $root "assets\healthycoach.ico"

$images = @()
foreach ($size in 16, 24, 32, 48, 64, 128, 256) {
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    $green = [System.Drawing.ColorTranslator]::FromHtml("#2f9e6e")
    $s = [single]$size
    $g.FillEllipse((New-Object System.Drawing.SolidBrush $green), $s * 0.03, $s * 0.03, $s * 0.94, $s * 0.94)

    # Leaf: two curves meeting at the tips, with a center vein.
    $leaf = New-Object System.Drawing.Drawing2D.GraphicsPath
    $top = New-Object System.Drawing.PointF ($s * 0.68), ($s * 0.22)
    $bottom = New-Object System.Drawing.PointF ($s * 0.30), ($s * 0.76)
    $leaf.AddBezier($bottom, (New-Object System.Drawing.PointF ($s * 0.18), ($s * 0.40)), (New-Object System.Drawing.PointF ($s * 0.45), ($s * 0.20)), $top)
    $leaf.AddBezier($top, (New-Object System.Drawing.PointF ($s * 0.78), ($s * 0.50)), (New-Object System.Drawing.PointF ($s * 0.55), ($s * 0.75)), $bottom)
    $g.FillPath([System.Drawing.Brushes]::White, $leaf)
    $vein = New-Object System.Drawing.Pen $green, ([Math]::Max(1, $s * 0.045))
    $g.DrawLine($vein, $bottom, (New-Object System.Drawing.PointF ($s * 0.60), ($s * 0.32)))
    $g.Dispose()

    $stream = New-Object System.IO.MemoryStream
    $bmp.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $images += , @($size, $stream.ToArray())
    $bmp.Dispose()
}

$out = New-Object System.IO.MemoryStream
$w = New-Object System.IO.BinaryWriter $out
$w.Write([UInt16]0); $w.Write([UInt16]1); $w.Write([UInt16]$images.Count)
$offset = 6 + 16 * $images.Count
foreach ($img in $images) {
    $dim = if ($img[0] -ge 256) { 0 } else { $img[0] }
    $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([UInt16]1); $w.Write([UInt16]32)
    $w.Write([UInt32]$img[1].Length); $w.Write([UInt32]$offset)
    $offset += $img[1].Length
}
foreach ($img in $images) { $w.Write($img[1]) }
$w.Flush()
[System.IO.File]::WriteAllBytes($icoPath, $out.ToArray())
Write-Output "Icon written: $icoPath"
