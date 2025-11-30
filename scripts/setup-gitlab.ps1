# AutoPipe - GitLab Setup Script for Windows (PowerShell)
# Creates admin token and runner registration token automatically

$ErrorActionPreference = "Stop"

$GITLAB_URL = if ($env:GITLAB_URL) { $env:GITLAB_URL } else { "http://localhost:8080" }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AutoPipe - GitLab Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Wait-ForGitLab {
    Write-Host "[INFO] Waiting for GitLab to be ready..." -ForegroundColor Yellow
    $maxAttempts = 90
    $attempt = 0

    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "$GITLAB_URL/-/health" -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "[OK] GitLab is ready!" -ForegroundColor Green
                return $true
            }
        } catch {
            # Ignore errors, just retry
        }

        $attempt++
        Write-Host "[INFO] Waiting for GitLab... ($attempt/$maxAttempts)" -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }

    Write-Host "[ERROR] GitLab did not become ready in time" -ForegroundColor Red
    return $false
}

function Get-InitialRootPassword {
    Write-Host "[INFO] Getting initial root password..." -ForegroundColor Yellow

    try {
        $password = docker exec t1-gitlab-1 cat /etc/gitlab/initial_root_password 2>$null | Select-String "Password:" | ForEach-Object { $_.Line.Split()[1] }
        if ($password) {
            Write-Host "[OK] Found initial root password" -ForegroundColor Green
            return $password
        }
    } catch {
        # Ignore
    }

    Write-Host "[INFO] Could not get initial password" -ForegroundColor Yellow
    return $null
}

function New-AdminToken {
    Write-Host "[INFO] Creating admin access token..." -ForegroundColor Yellow

    $tokenName = "autopipe-admin-$(Get-Date -Format 'yyyyMMddHHmmss')"
    $tokenValue = "glpat-autopipe-admin-token"

    $rubyScript = @"
token = User.find_by_username('root').personal_access_tokens.create(
  name: '$tokenName',
  scopes: [:api, :read_user, :read_api, :read_repository, :write_repository, :read_registry, :write_registry, :sudo],
  expires_at: 365.days.from_now
)
token.set_token('$tokenValue')
token.save!
puts 'TOKEN_CREATED:$tokenValue'
"@

    try {
        $result = $rubyScript | docker exec -i t1-gitlab-1 gitlab-rails runner - 2>$null
        if ($result -match "TOKEN_CREATED:(.+)") {
            $token = $Matches[1]
            Write-Host "[OK] Admin token created" -ForegroundColor Green
            return $token
        }
    } catch {
        Write-Host "[ERROR] Failed to create token: $_" -ForegroundColor Red
    }

    return $null
}

function New-RunnerToken {
    param([string]$AdminToken)

    Write-Host "[INFO] Creating runner authentication token..." -ForegroundColor Yellow

    try {
        $headers = @{ "PRIVATE-TOKEN" = $AdminToken }
        $body = @{
            runner_type = "instance_type"
            description = "autopipe-runner"
            tag_list = "docker,autopipe"
            run_untagged = "true"
            locked = "false"
        }

        $response = Invoke-RestMethod -Uri "$GITLAB_URL/api/v4/user/runners" -Method Post -Headers $headers -Body $body -ErrorAction Stop

        if ($response.token) {
            Write-Host "[OK] Runner token created" -ForegroundColor Green
            return $response.token
        }
    } catch {
        Write-Host "[ERROR] Failed to create runner token: $_" -ForegroundColor Red
    }

    return $null
}

function Save-Tokens {
    param([string]$AdminToken, [string]$RunnerToken)

    $content = @"
# AutoPipe Tokens - Generated $(Get-Date)
# Use these for autopipe commands

GITLAB_ADMIN_TOKEN=$AdminToken
GITLAB_RUNNER_TOKEN=$RunnerToken
GITLAB_URL=$GITLAB_URL

# Example usage:
# python -m autopipe deploy <repo> -t $AdminToken
"@

    $content | Out-File -FilePath "tokens.env" -Encoding UTF8
    Write-Host "[OK] Tokens saved to tokens.env" -ForegroundColor Green
}

function Register-Runner {
    param([string]$RunnerToken)

    Write-Host "[INFO] Registering GitLab Runner..." -ForegroundColor Yellow

    try {
        docker exec t1-gitlab-runner-1 gitlab-runner register `
            --non-interactive `
            --url "http://gitlab" `
            --token $RunnerToken `
            --executor "docker" `
            --docker-image "docker:latest" `
            --docker-privileged `
            --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" `
            --docker-network-mode "t1_autopipe-net" `
            --description "autopipe-runner" `
            --tag-list "docker,autopipe"

        Write-Host "[OK] Runner registered successfully!" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[ERROR] Failed to register runner: $_" -ForegroundColor Red
        return $false
    }
}

# Main
Write-Host ""

if (-not (Wait-ForGitLab)) {
    Write-Host "[ERROR] Cannot continue without GitLab" -ForegroundColor Red
    exit 1
}

# Get root password
$rootPassword = Get-InitialRootPassword
if ($rootPassword) {
    Write-Host ""
    Write-Host "Initial root password: $rootPassword" -ForegroundColor Cyan
    Write-Host "(Save this - it will be deleted after first login)"
    Write-Host ""
}

# Create admin token
$adminToken = New-AdminToken
if (-not $adminToken) {
    Write-Host "[ERROR] Failed to create admin token" -ForegroundColor Red
    Write-Host "[INFO] You may need to create tokens manually in GitLab UI" -ForegroundColor Yellow
    exit 1
}

# Create runner token
$runnerToken = New-RunnerToken -AdminToken $adminToken

if ($runnerToken) {
    # Save tokens
    Save-Tokens -AdminToken $adminToken -RunnerToken $runnerToken

    # Register runner
    Register-Runner -RunnerToken $runnerToken

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Admin Token: $adminToken" -ForegroundColor Yellow
    Write-Host "Runner Token: $runnerToken" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Use AutoPipe:" -ForegroundColor Cyan
    Write-Host "  python -m autopipe deploy <repo_url> -t $adminToken" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "[WARN] Could not create runner token automatically" -ForegroundColor Yellow
    Write-Host "[INFO] Please create runner manually:" -ForegroundColor Yellow
    Write-Host "  1. Go to $GITLAB_URL/admin/runners" -ForegroundColor White
    Write-Host "  2. Click 'New instance runner'" -ForegroundColor White
    Write-Host "  3. Copy the token" -ForegroundColor White
}
