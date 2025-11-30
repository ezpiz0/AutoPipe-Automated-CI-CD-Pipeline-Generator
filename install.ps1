# AutoPipe - Installation Script for Windows (PowerShell)
# Команда 43 - T1 Challenge 2025

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AutoPipe - CI/CD Pipeline Generator" -ForegroundColor Cyan
Write-Host "Installation Script for Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

# Check for winget
$hasWinget = Get-Command winget -ErrorAction SilentlyContinue

# Check Python
Write-Info "Step 1/4: Checking Python..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Warn "Python not found!"
    if ($hasWinget) {
        Write-Info "Installing Python via winget..."
        winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } else {
        Write-Err "Please install Python 3.9+ from https://www.python.org/downloads/"
        Write-Info "Make sure to check 'Add Python to PATH' during installation"
        Read-Host "Press Enter after installing Python"
    }
}
Write-Host ""

# Check Git
Write-Info "Step 2/4: Checking Git..."
try {
    $gitVersion = git --version 2>&1
    Write-Host "[OK] $gitVersion" -ForegroundColor Green
} catch {
    Write-Warn "Git not found!"
    if ($hasWinget) {
        Write-Info "Installing Git via winget..."
        winget install Git.Git --accept-source-agreements --accept-package-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } else {
        Write-Err "Please install Git from https://git-scm.com/download/win"
        Read-Host "Press Enter after installing Git"
    }
}
Write-Host ""

# Check Docker
Write-Info "Step 3/4: Checking Docker..."
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "[OK] $dockerVersion" -ForegroundColor Green
} catch {
    Write-Warn "Docker not found!"
    if ($hasWinget) {
        Write-Info "Installing Docker Desktop via winget..."
        winget install Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
        Write-Warn "Please start Docker Desktop after installation"
    } else {
        Write-Err "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    }
    Read-Host "Press Enter after Docker Desktop is running"
}
Write-Host ""

# Install Python dependencies
Write-Info "Step 4/4: Installing Python dependencies..."

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Info "Creating virtual environment..."
    python -m venv venv
}

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -e .

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[OK] Installation completed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start CI/CD infrastructure:"
Write-Host "  docker-compose up -d" -ForegroundColor Yellow
Write-Host ""
Write-Host "To use AutoPipe:"
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "  python -m autopipe analyze <repo_url>" -ForegroundColor Yellow
Write-Host "  python -m autopipe generate <repo_url> -o output/" -ForegroundColor Yellow
Write-Host ""
Write-Host "For full documentation, see README.md"
Write-Host ""
