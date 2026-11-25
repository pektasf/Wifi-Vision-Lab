@echo off
setlocal
cd /d "%~dp0"
title WiFi Vision Lab

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
    ) else (
        set "PY=python"
    )
) else (
    set "PY=python"
)

if "%PY%"=="python" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.10+ gerekli: https://www.python.org/downloads/windows/
        goto error
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Ilk kurulum yapiliyor...
    %PY% -m venv .venv
    if errorlevel 1 goto error
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo Python 3.10 veya daha yeni bir surum gerekli.
    goto error
)

".venv\Scripts\python.exe" -c "import hashlib; from pathlib import Path; Path('.venv/requirements.current').write_text(hashlib.sha256(Path('requirements.txt').read_bytes()).hexdigest(), encoding='ascii')"
if errorlevel 1 goto error

if not exist ".venv\requirements.sha256" goto install_deps
fc /b ".venv\requirements.sha256" ".venv\requirements.current" >nul
if errorlevel 1 goto install_deps
".venv\Scripts\python.exe" -c "import streamlit,pandas,plotly" >nul 2>nul
if errorlevel 1 goto install_deps
goto launch

:install_deps
echo Paketler kuruluyor veya requirements.txt degismis...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error
copy /y ".venv\requirements.current" ".venv\requirements.sha256" >nul

:launch
del ".venv\requirements.current" >nul 2>nul
echo WiFi Vision Lab baslatiliyor...
echo Yerel erisim: http://127.0.0.1:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
if errorlevel 1 goto error
pause
exit /b 0

:error
echo Baslatma hatasi. Python kurulumunu ve internet baglantisini kontrol edin.
pause
exit /b 1
