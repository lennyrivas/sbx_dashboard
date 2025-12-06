@echo off
cd /d "%~dp0"

REM путь к portable Python
set PYDIR=py311_emb

REM использование локального pip/streamlit
"%PYDIR%\python.exe" -m streamlit run main.py --server.headless=false

pause
