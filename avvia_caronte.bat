@echo off
REM Avvia CaronteApp su porta 5002 - Windows
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Venv non trovato. Esegui prima: python setup.py
    pause
    exit /b 1
)

echo.
echo Sincronizzazione DB con Google Drive...
python sync_db.py scarica
echo.

echo Avvio CaronteApp su http://localhost:5002
echo Per fermare: CTRL+C
echo.

python app.py

echo.
echo Carico DB aggiornato su Drive...
python sync_db.py carica
echo.
echo Arrivederci!
pause
