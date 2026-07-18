#Requires -Version 5.1
<#
.SYNOPSIS
    Compiles retro-amp into a standalone Windows binary with Nuitka.

.DESCRIPTION
    Produces a self-contained --standalone build (no Python install needed on
    the target machine). Output: dist\retro-amp\retro-amp.exe plus its DLLs,
    and a zipped dist\retro-amp-vX.Y.Z-win64.zip ready to hand out.

    Audio note: retro-amp depends on pygame, mutagen, pyogg and miniaudio.
    pyogg loads its native ogg/vorbis/opus libraries via ctypes at runtime,
    so its package data is included explicitly (--include-package-data=pyogg).
    If playback fails in the compiled binary, that is the first place to look.
#>

$ErrorActionPreference = "Stop"

# Pfade - alles relativ zum Skriptverzeichnis, damit der Aufruf ortsunabhaengig ist
$root    = $PSScriptRoot
$entry   = Join-Path $root "src\retro_amp\__main__.py"
$initPy  = Join-Path $root "src\retro_amp\__init__.py"
$outDir  = Join-Path $root "dist"
$distDir = Join-Path $outDir "retro-amp"

# venv-Python bevorzugen, sonst System-Python
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

# venv mit dem Lockfile abgleichen, damit Nuitka keine veralteten
# (Git-)Dependencies einkompiliert. --inexact laesst Extra-Pakete wie das
# ad-hoc installierte nuitka unangetastet.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "Syncing venv to lockfile (uv sync --inexact)..." -ForegroundColor Cyan
    & uv sync --inexact --project $root
    if ($LASTEXITCODE -ne 0) { throw "uv sync fehlgeschlagen" }
} else {
    Write-Host "uv nicht gefunden - venv-Sync uebersprungen" -ForegroundColor Yellow
}

# Version aus __init__.py lesen, damit die EXE-Metadaten nicht von pyproject driften
$version = ([regex]'__version__\s*=\s*"([^"]+)"').Match((Get-Content -Raw $initPy)).Groups[1].Value
if (-not $version) { throw "Konnte __version__ nicht aus $initPy lesen" }

Write-Host "Compiling retro-amp v$version with Nuitka..." -ForegroundColor Cyan

# Alten Build verwerfen - das Ergebnis soll reproduzierbar sein
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }

$started = Get-Date

# --standalone        : self-contained, kein Python auf dem Zielrechner noetig
# --remove-output     : C-/Objekt-Zwischendateien nach dem Build aufraeumen
# --include-package-data=retro_amp : locale\*.json mitnehmen
# --include-package-data=pyogg     : die per ctypes geladenen Audio-Libs mitnehmen
# (kein --windows-console-mode: Default behaelt die Konsole - noetig fuer das TUI)
# Nuitka als Build-Tool sicherstellen (kein Dev-Dep, wird ad-hoc installiert).
# 'uv sync' ohne --inexact entfernt es wieder, daher: nach jedem Sync pruefen.
& $python -m nuitka --version 2>$null 1>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nuitka fehlt im venv - installiere..." -ForegroundColor Yellow
    & uv pip install nuitka
    if ($LASTEXITCODE -ne 0) { throw "Nuitka-Installation fehlgeschlagen" }
}

# Nuitka-Argumente sammeln, damit das App-Icon konditional angehaengt werden kann
$nuitkaArgs = @(
    "--standalone"
    "--assume-yes-for-downloads"
    "--remove-output"
    "--include-package=retro_amp"
    "--include-package-data=retro_amp"
    "--include-package-data=pyogg"
    "--output-dir=$outDir"
    "--output-filename=retro-amp.exe"
    "--company-name=Michael Blaess"
    "--product-name=retro-amp"
    "--file-version=$version"
    "--product-version=$version"
)

# App-Icon in die EXE einbetten (assets\icon.ico, multi-resolution).
$iconPath = Join-Path $root "assets\icon.ico"
if (Test-Path $iconPath) {
    $nuitkaArgs += "--windows-icon-from-ico=$iconPath"
} else {
    Write-Host "Hinweis: $iconPath fehlt - EXE wird ohne Icon gebaut." -ForegroundColor Yellow
}

& $python -m nuitka @nuitkaArgs $entry

if ($LASTEXITCODE -ne 0) { throw "Nuitka-Build fehlgeschlagen (Exit $LASTEXITCODE)" }

# Nuitka benennt den dist-Ordner nach dem Hauptmodul (__main__.dist) - umbenennen
$nuitkaDist = Join-Path $outDir "__main__.dist"
if (Test-Path $nuitkaDist) { Rename-Item -Path $nuitkaDist -NewName "retro-amp" }

# fpcalc (Chromaprint) neben die EXE legen - die Auto-Titel-Funktion (AcoustID)
# findet es zur Laufzeit neben retro-amp.exe. Nur wenn auf dem Build-Rechner
# vorhanden; sonst laeuft die App ohne AcoustID (MusicBrainz bleibt nutzbar).
$fpcalc = (Get-Command fpcalc -ErrorAction SilentlyContinue).Source
if ($fpcalc -and (Test-Path $fpcalc)) {
    Copy-Item -Path $fpcalc -Destination (Join-Path $distDir "fpcalc.exe") -Force
    Write-Host "fpcalc gebuendelt: $fpcalc" -ForegroundColor Cyan
} else {
    Write-Host "Hinweis: fpcalc nicht gefunden - Build ohne AcoustID-Fingerprint." -ForegroundColor Yellow
}

$elapsed = [int]((Get-Date) - $started).TotalSeconds
$exe     = Join-Path $distDir "retro-amp.exe"
$sizeMB  = [math]::Round(((Get-ChildItem -Recurse $distDir | Measure-Object Length -Sum).Sum) / 1MB, 1)

# Verteilbares ZIP erzeugen - der Top-Level-Ordner bleibt im Archiv erhalten,
# der Empfaenger entpackt also direkt einen sauberen retro-amp-Ordner
$zip = Join-Path $outDir "retro-amp-v$version-win64.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path $distDir -DestinationPath $zip
$zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)

Write-Host ""
Write-Host "Done in ${elapsed}s" -ForegroundColor Green
Write-Host "  dist folder : $distDir  (${sizeMB} MB)"
Write-Host "  zip         : $zip  (${zipMB} MB)"
Write-Host "  run         : $exe"
