@echo off
REM Demarrage en un clic (Windows) : double-cliquez sur ce fichier.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 n'est pas installe. Telechargez-le sur https://www.python.org/downloads/
    echo IMPORTANT : cochez "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)

if not exist .venv (
    echo Premiere installation, patientez une minute...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo.
echo ------------------------------------------------------
echo   Refuge Immo demarre.
echo   Ouvrez votre navigateur sur :  http://localhost:8000
echo   (fermez cette fenetre pour arreter)
echo ------------------------------------------------------
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
