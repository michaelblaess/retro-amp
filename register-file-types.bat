@echo off
REM ============================================================
REM  retro-amp - Dateiverknuepfung registrieren
REM
REM  Registriert retro-amp als Audio-Player in Windows.
REM  Kein Administrator noetig (nutzt HKCU).
REM
REM  Fuer die vollstaendige Registrierung die .ps1-Variante
REM  verwenden (RegisteredApplications + Capabilities).
REM ============================================================

set APP_NAME=retro-amp
set PROG_ID=retro-amp.AudioFile

REM --- retro-amp.exe finden ---
set EXE_PATH=
if exist "%~dp0.venv\Scripts\%APP_NAME%.exe" (
    set "EXE_PATH=%~dp0.venv\Scripts\%APP_NAME%.exe"
) else if exist "%ProgramFiles%\%APP_NAME%\%APP_NAME%.exe" (
    set "EXE_PATH=%ProgramFiles%\%APP_NAME%\%APP_NAME%.exe"
) else (
    where %APP_NAME% >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "delims=" %%i in ('where %APP_NAME%') do set "EXE_PATH=%%i"
    )
)

if "%EXE_PATH%"=="" (
    echo %APP_NAME%.exe nicht gefunden!
    echo Bitte zuerst setup.bat oder install.ps1 ausfuehren.
    pause
    exit /b 1
)

echo Gefunden: %EXE_PATH%
echo.

REM --- Icon ---
set "ICON_PATH=%~dp0retro-amp.ico"
if not exist "%ICON_PATH%" set "ICON_PATH=%EXE_PATH%"

REM --- ProgId registrieren (HKCU, kein Admin noetig) ---
echo Registriere ProgId...
reg add "HKCU\SOFTWARE\Classes\%PROG_ID%" /ve /d "%APP_NAME% Audio File" /f >nul
reg add "HKCU\SOFTWARE\Classes\%PROG_ID%\shell\open\command" /ve /d "\"%EXE_PATH%\" \"%%1\"" /f >nul
reg add "HKCU\SOFTWARE\Classes\%PROG_ID%\DefaultIcon" /ve /d "\"%ICON_PATH%\"" /f >nul

REM --- Capabilities ---
echo Registriere Capabilities...
reg add "HKCU\SOFTWARE\%APP_NAME%\Capabilities" /v "ApplicationName" /d "%APP_NAME%" /f >nul
reg add "HKCU\SOFTWARE\%APP_NAME%\Capabilities" /v "ApplicationDescription" /d "Terminal music player with retro charm" /f >nul

for %%e in (.mp3 .m4a .ogg .oga .opus .flac .wav) do (
    reg add "HKCU\SOFTWARE\%APP_NAME%\Capabilities\FileAssociations" /v "%%e" /d "%PROG_ID%" /f >nul
)

REM --- RegisteredApplications ---
echo Registriere als Windows-Anwendung...
reg add "HKCU\SOFTWARE\RegisteredApplications" /v "%APP_NAME%" /d "SOFTWARE\%APP_NAME%\Capabilities" /f >nul

REM --- OpenWithProgids ---
echo Registriere Dateiendungen...
for %%e in (.mp3 .m4a .ogg .oga .opus .flac .wav) do (
    reg add "HKCU\SOFTWARE\Classes\%%e\OpenWithProgids" /v "%PROG_ID%" /t REG_NONE /d "" /f >nul
    echo   %%e
)

echo.
echo Fertig! retro-amp ist registriert.
echo.
echo Oeffne Windows-Einstellungen...
echo Bitte dort retro-amp fuer die gewuenschten Dateitypen auswaehlen.
echo.
start ms-settings:defaultapps
pause
