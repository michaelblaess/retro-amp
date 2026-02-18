@echo off
echo === retro-amp Setup ===
echo.

if not exist ".venv" (
    echo Erstelle virtuelle Umgebung...
    python -m venv .venv
)

echo Aktiviere .venv...
call .venv\Scripts\activate.bat

echo Aktualisiere pip...
python -m pip install --upgrade pip >nul 2>&1

echo Installiere retro-amp mit Dev-Dependencies...
pip install -e ".[dev]"

echo.
echo === Setup abgeschlossen ===
echo Starte mit: run.bat
