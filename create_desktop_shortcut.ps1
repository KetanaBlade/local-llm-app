$WshShell = New-Object -ComObject WScript.Shell
$AppDir = $PSScriptRoot

# Determine Desktop directory
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
if (-not $DesktopPath -or -not (Test-Path $DesktopPath)) {
    if ($env:USERPROFILE -and (Test-Path "$env:USERPROFILE\Desktop")) {
        $DesktopPath = "$env:USERPROFILE\Desktop"
    } elseif (Test-Path "C:\Users\Stardust\Desktop") {
        $DesktopPath = "C:\Users\Stardust\Desktop"
    } else {
        $DesktopPath = $AppDir
    }
}

$Targets = @(
    (Join-Path $AppDir "Local AI Studio.lnk"),
    (Join-Path $DesktopPath "Local AI Studio.lnk")
)

$EdgeIcon = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $EdgeIcon)) {
    $EdgeIcon = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
}

foreach ($target in $Targets) {
    try {
        $Shortcut = $WshShell.CreateShortcut($target)
        $Shortcut.TargetPath = "wscript.exe"
        $Shortcut.Arguments = "`"$AppDir\Launch-Studio.vbs`""
        $Shortcut.WorkingDirectory = $AppDir
        $Shortcut.Description = "Local AI Studio - 100% On-Device AI with Voice, Vision & Document Creation"
        if (Test-Path $EdgeIcon) {
            $Shortcut.IconLocation = "$EdgeIcon,0"
        }
        $Shortcut.Save()
        Write-Host "Created shortcut: $target"
    } catch {
        Write-Host "Could not write to $target : $_"
    }
}
