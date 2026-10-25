@echo off
setlocal
cd /d "%~dp0"

echo ERSELMETZ AI - Windows installer build
echo ======================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python 3.14 x64 is required in .venv.
    goto :failed
)
where node.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js 22.12 or later is required.
    goto :failed
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm.cmd was not found.
    goto :failed
)

".venv\Scripts\python.exe" -c "import struct, sys; sys.exit(0 if sys.version_info[:2] == (3, 14) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo ERROR: .venv must use Python 3.14 x64.
    goto :failed
)
node.exe -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major > 22 || (major === 22 && minor >= 12) ? 0 : 1)"
if errorlevel 1 (
    echo ERROR: Node.js 22.12 or later is required.
    goto :failed
)
node.exe -e "process.exit(process.platform === 'win32' && process.arch === 'x64' ? 0 : 1)"
if errorlevel 1 (
    echo ERROR: This build supports Windows x64 only.
    goto :failed
)

if /i "%~1"=="--check" (
    echo Prerequisites are ready. No build was started.
    exit /b 0
)

echo This local build may download locked npm and Python build dependencies.
echo It will create an UNSIGNED installer; it will not publish or install the app.
choice /c YN /n /m "Continue? [Y/N] "
if errorlevel 2 (
    echo Build cancelled.
    pause
    exit /b 0
)

echo.
echo [1/4] Installing desktop UI dependencies...
call npm.cmd --prefix desktop-ui ci
if errorlevel 1 goto :failed

echo.
echo [2/4] Building desktop UI...
call npm.cmd --prefix desktop-ui run build
if errorlevel 1 goto :failed

echo.
echo [3/4] Packaging Python backend...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "desktop\scripts\build-backend.ps1"
if errorlevel 1 goto :failed

echo.
echo [4/4] Building Windows installer...
call npm.cmd --prefix desktop ci
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "desktop\scripts\build-installer.ps1"
if errorlevel 1 goto :failed

for /f "delims=" %%V in ('node.exe -p "require('./desktop/package.json').version"') do set "APP_VERSION=%%V"
set "INSTALLER=desktop\release\ERSELMETZ-AI-Setup-%APP_VERSION%-win-x64.exe"
if not exist "%INSTALLER%" (
    echo ERROR: Build finished, but the expected installer was not found.
    goto :failed
)

echo.
echo Build complete: "%CD%\%INSTALLER%"
echo Double-click that installer to install ERSELMETZ AI.
pause
exit /b 0

:failed
echo.
echo Build stopped. Review the error above; no installer was published.
pause
exit /b 1
