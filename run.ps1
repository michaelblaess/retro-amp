if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" -m retro_amp @args
} else {
    & python -m retro_amp @args
}
