@echo off
REM AutoPipe - Installation Script for Windows
REM Команда 43 - T1 Challenge 2025

echo ==========================================
echo AutoPipe - CI/CD Pipeline Generator
echo Installation Script for Windows
echo ==========================================
echo.

REM Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Running without administrator privileges.
    echo [WARN] Some installations may require admin rights.
    echo.
)

REM Check Python
echo [INFO] Step 1/4: Checking Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Python not found!
    echo [INFO] Please install Python 3.9+ from https://www.python.org/downloads/
    echo [INFO] Make sure to check "Add Python to PATH" during installation
    echo.
    echo [INFO] After installing Python, run this script again.
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [OK] Python installed: %PYTHON_VERSION%
)
echo.

REM Check Git
echo [INFO] Step 2/4: Checking Git...
git --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Git not found!
    echo [INFO] Please install Git from https://git-scm.com/download/win
    echo.
    echo [INFO] After installing Git, run this script again.
    pause
    exit /b 1
) else (
    for /f "tokens=3" %%i in ('git --version 2^>^&1') do set GIT_VERSION=%%i
    echo [OK] Git installed: %GIT_VERSION%
)
echo.

REM Check Docker
echo [INFO] Step 3/4: Checking Docker...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Docker not found!
    echo [INFO] Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo [INFO] Make sure Docker Desktop is running after installation
    echo.
    echo [INFO] After installing Docker, run this script again.
    pause
    exit /b 1
) else (
    for /f "tokens=3" %%i in ('docker --version 2^>^&1') do set DOCKER_VERSION=%%i
    echo [OK] Docker installed: %DOCKER_VERSION%
)
echo.

REM Install Python dependencies
echo [INFO] Step 4/4: Installing Python dependencies...

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment and install dependencies
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .

echo.
echo ==========================================
echo [OK] Installation completed!
echo ==========================================
echo.
echo To start CI/CD infrastructure:
echo   docker-compose up -d
echo.
echo To use AutoPipe:
echo   venv\Scripts\activate.bat
echo   python -m autopipe analyze ^<repo_url^>
echo   python -m autopipe generate ^<repo_url^> -o output/
echo.
echo For full documentation, see README.md
echo.
pause
