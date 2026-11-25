@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Once START.bat dosyasini calistirin.& pause & exit /b 1)
".venv\Scripts\python.exe" scripts\wifi_signal_monitor.py
pause
