# AutoPipe - Quick Start Script
# One command to start everything!

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AutoPipe - Quick Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "[INFO] Checking Docker..." -ForegroundColor Yellow
try {
    docker version | Out-Null
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not running!" -ForegroundColor Red
    Write-Host "[INFO] Please start Docker Desktop and run this script again" -ForegroundColor Yellow
    exit 1
}

# Start containers
Write-Host ""
Write-Host "[INFO] Starting CI/CD infrastructure..." -ForegroundColor Yellow
docker-compose up -d

# Wait for containers to start
Write-Host "[INFO] Waiting for containers to initialize (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Run setup
Write-Host ""
Write-Host "[INFO] Setting up GitLab (this may take several minutes)..." -ForegroundColor Yellow
Write-Host "[INFO] GitLab needs time to fully initialize on first start" -ForegroundColor Yellow
Write-Host ""

& "$PSScriptRoot\setup-gitlab.ps1"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Quick Start Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services running at:" -ForegroundColor Cyan
Write-Host "  GitLab:    http://localhost:8080" -ForegroundColor White
Write-Host "  SonarQube: http://localhost:9000" -ForegroundColor White
Write-Host "  Nexus:     http://localhost:8081" -ForegroundColor White
Write-Host ""
Write-Host "Check tokens.env for your API tokens" -ForegroundColor Yellow
Write-Host ""
