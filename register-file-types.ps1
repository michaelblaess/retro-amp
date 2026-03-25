# ============================================================
#  retro-amp - Dateiverknuepfung registrieren (PowerShell)
#
#  Registriert retro-amp als Audio-Player in Windows ueber
#  RegisteredApplications + Capabilities (wie WinRAR, VLC etc.).
#
#  Kein Administrator noetig! Nutzt HKCU (User-Ebene).
#
#  Verwendung:
#    powershell -ExecutionPolicy Bypass -File register-file-types.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$AppName = "retro-amp"
$ProgId = "retro-amp.AudioFile"
$Description = "retro-amp — Terminal music player with retro charm"
$Extensions = @(".mp3", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".wav")

Write-Host ""
Write-Host "  retro-amp - Dateiverknuepfung / File Association" -ForegroundColor Cyan
Write-Host ""

# --- retro-amp.exe finden ---
$ExePath = $null

# 1. Installiert (Program Files)
$candidate = Join-Path $env:ProgramFiles "$AppName\$AppName.exe"
if (Test-Path $candidate) { $ExePath = $candidate }

# 2. Dev-Umgebung (.venv)
if (-not $ExePath) {
    $candidate = Join-Path $PSScriptRoot ".venv\Scripts\$AppName.exe"
    if (Test-Path $candidate) { $ExePath = $candidate }
}

# 3. Im PATH
if (-not $ExePath) {
    $inPath = Get-Command $AppName -ErrorAction SilentlyContinue
    if ($inPath) { $ExePath = $inPath.Source }
}

if (-not $ExePath) {
    Write-Host "  [FEHLER] $AppName.exe nicht gefunden!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Gesucht in:"
    Write-Host "    - $env:ProgramFiles\$AppName\"
    Write-Host "    - $PSScriptRoot\.venv\Scripts\"
    Write-Host "    - PATH"
    Write-Host ""
    Write-Host "  Bitte zuerst installieren (install.ps1 oder setup.bat)."
    Read-Host "  Enter zum Beenden"
    exit 1
}

Write-Host "  Gefunden: $ExePath" -ForegroundColor Green
Write-Host ""

# --- Icon suchen ---
$IconPath = Join-Path $PSScriptRoot "retro-amp.ico"
if (-not (Test-Path $IconPath)) {
    # Fallback: EXE selbst als Icon-Quelle
    $IconPath = $ExePath
}
Write-Host "  Icon: $IconPath"
Write-Host ""

# --- 1. ProgId registrieren (HKCU) ---
Write-Host "  Registriere ProgId: $ProgId"

$progIdPath = "HKCU:\SOFTWARE\Classes\$ProgId"
New-Item -Path $progIdPath -Force | Out-Null
Set-ItemProperty -Path $progIdPath -Name "(Default)" -Value "$AppName Audio File"

# Open-Kommando
$cmdPath = "$progIdPath\shell\open\command"
New-Item -Path $cmdPath -Force | Out-Null
Set-ItemProperty -Path $cmdPath -Name "(Default)" -Value "`"$ExePath`" `"%1`""

# Icon
$iconRegPath = "$progIdPath\DefaultIcon"
New-Item -Path $iconRegPath -Force | Out-Null
if ($IconPath -like "*.ico") {
    Set-ItemProperty -Path $iconRegPath -Name "(Default)" -Value "`"$IconPath`""
} else {
    Set-ItemProperty -Path $iconRegPath -Name "(Default)" -Value "`"$IconPath`",0"
}

Write-Host "  [OK] ProgId registriert" -ForegroundColor Green

# --- 2. Capabilities registrieren ---
Write-Host "  Registriere Capabilities"

$capPath = "HKCU:\SOFTWARE\$AppName\Capabilities"
New-Item -Path $capPath -Force | Out-Null
Set-ItemProperty -Path $capPath -Name "ApplicationName" -Value $AppName
Set-ItemProperty -Path $capPath -Name "ApplicationDescription" -Value $Description

# FileAssociations
$faPath = "$capPath\FileAssociations"
New-Item -Path $faPath -Force | Out-Null
foreach ($ext in $Extensions) {
    Set-ItemProperty -Path $faPath -Name $ext -Value $ProgId
}

Write-Host "  [OK] Capabilities registriert" -ForegroundColor Green

# --- 3. RegisteredApplications ---
Write-Host "  Registriere als Windows-Anwendung"

$regAppsPath = "HKCU:\SOFTWARE\RegisteredApplications"
if (-not (Test-Path $regAppsPath)) {
    New-Item -Path $regAppsPath -Force | Out-Null
}
Set-ItemProperty -Path $regAppsPath -Name $AppName -Value "SOFTWARE\$AppName\Capabilities"

Write-Host "  [OK] Registriert" -ForegroundColor Green

# --- 4. OpenWithProgids fuer jede Extension ---
Write-Host "  Registriere OpenWithProgids:"
foreach ($ext in $Extensions) {
    $extPath = "HKCU:\SOFTWARE\Classes\$ext\OpenWithProgids"
    New-Item -Path $extPath -Force | Out-Null
    Set-ItemProperty -Path $extPath -Name $ProgId -Value ([byte[]]@()) -Type Binary
    Write-Host "    $ext" -ForegroundColor Green
}

# --- 5. Explorer benachrichtigen ---
$code = @"
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int wEventId, int uFlags, System.IntPtr dwItem1, System.IntPtr dwItem2);
"@
$shell = Add-Type -MemberDefinition $code -Name "ShellNotify" -Namespace "Win32" -PassThru
$shell::SHChangeNotify(0x08000000, 0, [System.IntPtr]::Zero, [System.IntPtr]::Zero)

Write-Host ""
Write-Host "  [OK] Registrierung abgeschlossen!" -ForegroundColor Green
Write-Host ""
Write-Host "  Registrierte Formate: $($Extensions -join ', ')"
Write-Host ""

# --- 6. Windows-Einstellungen oeffnen ---
Write-Host "  Oeffne Windows-Einstellungen..." -ForegroundColor Yellow
Write-Host "  Bitte dort retro-amp fuer die gewuenschten Dateitypen auswaehlen."
Write-Host ""

Start-Process "ms-settings:defaultapps"

Write-Host "  Zum Entfernen:" -ForegroundColor Gray
Write-Host "    Remove-Item -Recurse 'HKCU:\SOFTWARE\Classes\$ProgId'" -ForegroundColor Gray
Write-Host "    Remove-Item -Recurse 'HKCU:\SOFTWARE\$AppName'" -ForegroundColor Gray
Write-Host "    Remove-ItemProperty 'HKCU:\SOFTWARE\RegisteredApplications' -Name '$AppName'" -ForegroundColor Gray
Write-Host ""
Read-Host "  Enter zum Beenden"
