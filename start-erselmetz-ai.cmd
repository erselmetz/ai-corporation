@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
 echo Python environment missing. Create .venv and install requirements.txt first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets" >nul 2>&1
if errorlevel 1 (
 echo Qt is missing. Run .venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
 pause
 exit /b 1
)
start "" /b ".venv\Scripts\pythonw.exe" -m app.native_desktop %*
