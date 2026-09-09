@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   GMP Automation System - Online Start
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Create the private configuration file from the safe template.
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    if errorlevel 1 (
        echo [ERROR] Failed to create the .env configuration file.
        pause
        exit /b 1
    )
)

REM Ask only when an API key has not already been saved in .env.
findstr /r /c:"^ANTHROPIC_API_KEY=." ".env" >nul
if not errorlevel 1 goto api_key_ready

echo.
echo An Anthropic API key is required for Online OCR.
echo Create or copy a key from: https://console.anthropic.com/settings/keys
echo Paste the key when prompted. It will be hidden and saved only in this folder.
powershell -NoProfile -Command "$envFile = Join-Path (Get-Location) '.env'; $secureKey = Read-Host 'Paste your Anthropic API key' -AsSecureString; $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey); try { $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }; if ([string]::IsNullOrWhiteSpace($key)) { exit 1 }; [IO.File]::WriteAllText($envFile, ('ANTHROPIC_API_KEY=' + $key + [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))"
if errorlevel 1 (
    echo [ERROR] No API key was saved. The application cannot start.
    pause
    exit /b 1
)

:api_key_ready
echo [OK] Anthropic API key configuration found.

REM Check if poppler is available
where pdftoppm >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Poppler is not installed!
    echo PDF processing requires Poppler. Please install it:
    echo   1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
    echo   2. Extract to C:\poppler
    echo   3. Add C:\poppler\Library\bin to your system PATH
    echo.
)

REM Install Python dependencies
echo [1/2] Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some packages may have failed to install.
)

echo.
echo [2/2] Starting GMP Automation System with Waitress WSGI...
echo.
echo ============================================================
echo   Open your browser and go to: http://localhost:5001/online
echo   Press Ctrl+C to stop the server.
echo ============================================================
echo.

waitress-serve --host=0.0.0.0 --port=5001 app:app
pause
