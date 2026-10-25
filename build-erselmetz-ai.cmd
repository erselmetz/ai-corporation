@echo off
cd /d "%~dp0"
echo ERSELMETZ AI - native Python build (no Node.js or Electron)
if not exist ".venv\Scripts\python.exe" (
 echo Python environment missing. Create .venv and install requirements.txt first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" tools\build_native.py
if errorlevel 1 (
 echo Build failed. Nothing was installed or published.
 pause
 exit /b 1
)
pause
