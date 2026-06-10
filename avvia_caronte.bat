@echo off
REM Avvia CaronteApp su porta 5002 (Windows)
cd /d "%~dp0"

REM Attiva venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Venv non trovato. Eseguire prima:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Avvio CaronteApp su http://localhost:5002
python app.py
pause
