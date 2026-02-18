@echo off
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m retro_amp %*
) else (
    python -m retro_amp %*
)
