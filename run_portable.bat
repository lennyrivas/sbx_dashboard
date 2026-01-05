@echo off
cd /d "%~dp0"

echo ==========================================
echo  Uruchamianie Warehouse Dashboard (Portable)
echo ==========================================

REM 1. Ustawienie sciezki do bibliotek (folder libs)
if exist "libs" (
    echo [INFO] Wykryto folder 'libs'. Uzywanie lokalnych bibliotek.
    set PYTHONPATH=%~dp0libs;%PYTHONPATH%
)

REM 2. Szukanie Pythona (priorytet dla folderu py311_emb)
if exist "py311_emb\python.exe" (
    set PY_EXE=py311_emb\python.exe
) else (
    set PY_EXE=python.exe
)

REM 3. Uruchomienie
"%PY_EXE%" -m streamlit run main.py --server.headless=false

pause
