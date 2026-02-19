# ============================================================
#  retro-amp - Installer (PowerShell)
#
#  Verwendung / Usage:
#    irm https://github.com/michaelblaess/retro-amp/releases/latest/download/install.ps1 | iex
#
#  Laedt das neueste Release von GitHub herunter und installiert es.
#  Keine Abhaengigkeiten noetig (kein Python, kein Git).
#
#  Downloads the latest release from GitHub and installs it.
#  No dependencies needed (no Python, no Git).
#
#  Installiert nach / Installs to:
#    C:\Program Files\retro-amp\
# ============================================================

$ErrorActionPreference = "Stop"

$Repo = "michaelblaess/retro-amp"
$AppName = "retro-amp"
$InstallDir = Join-Path $env:ProgramFiles $AppName

Write-Host ""
Write-Host "  +================================================+" -ForegroundColor Cyan
Write-Host "  |   retro-amp - Installer                         |" -ForegroundColor Cyan
Write-Host "  +================================================+" -ForegroundColor Cyan
Write-Host ""

# --- Admin-Rechte pruefen ---
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  [FEHLER] Bitte als Administrator ausfuehren!" -ForegroundColor Red
    Write-Host "  [ERROR]  Please run as Administrator!"
    Write-Host ""
    Write-Host "  Rechtsklick auf PowerShell -> 'Als Administrator ausfuehren'"
    Write-Host "  Right-click PowerShell -> 'Run as Administrator'"
    exit 1
}

# --- Architektur erkennen ---
$Arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
$Artifact = "${AppName}-win-${Arch}"
$Archive = "${Artifact}.zip"

Write-Host "  Plattform / Platform: Windows ($Arch)"
Write-Host ""

# --- Neuestes Release von GitHub ermitteln ---
Write-Host "  Suche neuestes Release..."
$ApiUrl = "https://api.github.com/repos/${Repo}/releases/latest"

try {
    $Release = Invoke-RestMethod -Uri $ApiUrl -UseBasicParsing
} catch {
    Write-Host "  [FEHLER] Konnte GitHub API nicht erreichen." -ForegroundColor Red
    Write-Host "  Pruefe deine Internetverbindung."
    exit 1
}

$Asset = $Release.assets | Where-Object { $_.name -eq $Archive } | Select-Object -First 1

if (-not $Asset) {
    Write-Host "  [FEHLER] Kein Release fuer ${Archive} gefunden!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Verfuegbare Assets:"
    $Release.assets | ForEach-Object { Write-Host "    $($_.name)" }
    exit 1
}

$DownloadUrl = $Asset.browser_download_url
$Version = $Release.tag_name
Write-Host "  [OK] Release gefunden: $Version" -ForegroundColor Green
Write-Host ""

# --- Download ---
$TmpDir = Join-Path $env:TEMP "${AppName}-install"
if (Test-Path $TmpDir) { Remove-Item -Recurse -Force $TmpDir }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
$TmpFile = Join-Path $TmpDir $Archive

Write-Host "  Lade herunter / Downloading: $Archive"
try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TmpFile -UseBasicParsing
} catch {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $TmpFile)
}
Write-Host "  [OK] Download abgeschlossen / Download complete" -ForegroundColor Green
Write-Host ""

# --- Entpacken ---
Write-Host "  Entpacke nach / Extracting to: $InstallDir"

if (Test-Path $InstallDir) {
    $BackupDir = "${InstallDir}.bak"
    if (Test-Path $BackupDir) { Remove-Item -Recurse -Force $BackupDir }
    Rename-Item -Path $InstallDir -NewName "${InstallDir}.bak"
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Expand-Archive -Path $TmpFile -DestinationPath $InstallDir -Force
Remove-Item -Recurse -Force $TmpDir

$BackupDir = "${InstallDir}.bak"
if (Test-Path $BackupDir) { Remove-Item -Recurse -Force $BackupDir }

Write-Host "  [OK] Entpackt / Extracted" -ForegroundColor Green
Write-Host ""

# --- PATH ergaenzen ---
$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
if ($MachinePath -notlike "*$InstallDir*") {
    Write-Host "  Fuege zum PATH hinzu / Adding to PATH: $InstallDir" -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", "$InstallDir;$MachinePath", "Machine")
    $env:Path = "$InstallDir;$env:Path"
    Write-Host "  [OK] PATH aktualisiert / PATH updated" -ForegroundColor Green
}

# --- Fertig ---
Write-Host ""
Write-Host "  +================================================+" -ForegroundColor Green
Write-Host "  |   Installation abgeschlossen! ($Version)" -ForegroundColor Green
Write-Host "  +================================================+" -ForegroundColor Green
Write-Host ""
Write-Host "  Starten mit / Start with:"
Write-Host "    retro-amp" -ForegroundColor Cyan
Write-Host "    retro-amp D:\Musik" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Deinstallieren / Uninstall:" -ForegroundColor Gray
Write-Host "    Remove-Item -Recurse '$InstallDir'" -ForegroundColor Gray
Write-Host ""
Write-Host "  HINWEIS: Oeffne ein neues Terminal, damit der PATH wirkt." -ForegroundColor Yellow
Write-Host "  NOTE:    Open a new terminal for PATH to take effect." -ForegroundColor Yellow
Write-Host ""
