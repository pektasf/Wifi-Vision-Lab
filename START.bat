@echo off
setlocal
cd /d "%~dp0"
title WiFi Vision Lab

where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.10+ gerekli: https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    set "PY=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Ilk kurulum yapiliyor...
    %PY% -m venv .venv
    if errorlevel 1 goto error
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto error

".venv\Scripts\python.exe" -c "import streamlit,pandas,plotly" >nul 2>nul
if errorlevel 1 (
    echo Paketler kuruluyor...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto error
)

echo WiFi Vision Lab baslatiliyor...
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
pause
exit /b 0

:error
echo Baslatma hatasi.
pause
exit /b 1
