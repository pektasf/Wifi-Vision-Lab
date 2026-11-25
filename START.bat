@echo off
setlocal
cd /d "%~dp0"
title WiFi Vision Lab
where python >nul 2>nul
if errorlevel 1 (
 echo Python 3.10+ bulunamadi. https://www.python.org/downloads/windows/
 echo Kurulumda Add Python to PATH secenegini isaretleyin.
 pause
 exit /b 1
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (echo Python 3.10 veya ustu gerekli.& pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
 echo Yerel Python ortami olusturuluyor...
 python -m venv .venv
 if errorlevel 1 (echo venv olusturulamadi.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -c "import streamlit,pandas" >nul 2>nul
if errorlevel 1 (
 echo Gerekli paketler kuruluyor. Ilk kurulum icin internet gerekir...
 ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
 if errorlevel 1 (echo Paket kurulumu basarisiz.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
pause
