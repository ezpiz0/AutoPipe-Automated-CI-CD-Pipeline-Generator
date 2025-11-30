#!/bin/bash
# AutoPipe - GitLab Initial Setup Script
# Creates admin token and runner registration token automatically

set -e

GITLAB_URL="${GITLAB_URL:-http://localhost:8080}"
GITLAB_ROOT_PASSWORD="${GITLAB_ROOT_PASSWORD:-autopipe2025}"

echo "=========================================="
echo "AutoPipe - GitLab Setup"
echo "=========================================="

# Wait for GitLab to be fully ready
wait_for_gitlab() {
    echo "[INFO] Waiting for GitLab to be fully ready..."
    max_attempts=90
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        # Check health endpoint
        status=$(curl -s -o /dev/null -w "%{http_code}" "${GITLAB_URL}/-/health" 2>/dev/null || echo "000")

        if [ "$status" = "200" ]; then
            echo "[OK] GitLab is ready!"
            return 0
        fi

        attempt=$((attempt + 1))
        echo "[INFO] Waiting for GitLab... ($attempt/$max_attempts) - status: $status"
        sleep 10
    done

    echo "[ERROR] GitLab did not become ready in time"
    return 1
}

# Get root password from GitLab container
get_root_password() {
    echo "[INFO] Getting initial root password..."

    # Try to get password from container file
    local password
    password=$(docker exec t1-gitlab-1 cat /etc/gitlab/initial_root_password 2>/dev/null | grep "Password:" | awk '{print $2}' || echo "")

    if [ -n "$password" ]; then
        echo "[OK] Found initial root password"
        echo "$password"
        return 0
    fi

    # Fall back to default
    echo "[INFO] Using default password: $GITLAB_ROOT_PASSWORD"
    echo "$GITLAB_ROOT_PASSWORD"
}

# Create personal access token via Rails console
create_admin_token() {
    echo "[INFO] Creating admin access token..."

    local token_name="autopipe-admin-$(date +%s)"

    # Create token via Rails console
    docker exec -i t1-gitlab-1 gitlab-rails runner "
token = User.find_by_username('root').personal_access_tokens.create(
  name: '${token_name}',
  scopes: [:api, :read_user, :read_api, :read_repository, :write_repository, :read_registry, :write_registry, :sudo],
  expires_at: 365.days.from_now
)
token.set_token('glpat-autopipe-admin-token')
token.save!
puts 'TOKEN_CREATED:glpat-autopipe-admin-token'
" 2>/dev/null | grep "TOKEN_CREATED" | cut -d: -f2 || echo ""
}

# Create runner authentication token
create_runner_token() {
    local admin_token="$1"
    echo "[INFO] Creating runner authentication token..."

    # Create instance runner via API
    response=$(curl -s --request POST "${GITLAB_URL}/api/v4/user/runners" \
        --header "PRIVATE-TOKEN: ${admin_token}" \
        --data "runner_type=instance_type" \
        --data "description=autopipe-runner" \
        --data "tag_list=docker,autopipe" \
        --data "run_untagged=true" \
        --data "locked=false" 2>/dev/null)

    token=$(echo "$response" | grep -o '"token":"[^"]*"' | cut -d'"' -f4 || echo "")

    if [ -n "$token" ]; then
        echo "[OK] Runner token created: $token"
        echo "$token"
        return 0
    fi

    echo "[ERROR] Failed to create runner token"
    echo "[DEBUG] Response: $response"
    return 1
}

# Save tokens to file
save_tokens() {
    local admin_token="$1"
    local runner_token="$2"

    cat > tokens.env << EOF
# AutoPipe Tokens - Generated $(date)
# Use these for autopipe commands

GITLAB_ADMIN_TOKEN=${admin_token}
GITLAB_RUNNER_TOKEN=${runner_token}
GITLAB_URL=${GITLAB_URL}

# Example usage:
# python -m autopipe deploy <repo> -t \${GITLAB_ADMIN_TOKEN}
EOF

    echo "[OK] Tokens saved to tokens.env"
}

main() {
    wait_for_gitlab

    # Create admin token
    admin_token=$(create_admin_token)

    if [ -z "$admin_token" ]; then
        echo "[ERROR] Failed to create admin token"
        echo "[INFO] You may need to create tokens manually in GitLab UI"
        exit 1
    fi

    echo "[OK] Admin token: $admin_token"

    # Create runner token
    runner_token=$(create_runner_token "$admin_token")

    if [ -n "$runner_token" ]; then
        echo "[OK] Runner token: $runner_token"
        save_tokens "$admin_token" "$runner_token"

        echo ""
        echo "=========================================="
        echo "Setup Complete!"
        echo "=========================================="
        echo ""
        echo "Admin Token: $admin_token"
        echo "Runner Token: $runner_token"
        echo ""
        echo "Now register the runner:"
        echo "  export RUNNER_TOKEN=$runner_token"
        echo "  docker-compose restart gitlab-runner"
    else
        echo "[WARN] Could not create runner token automatically"
        echo "[INFO] Please create runner manually in GitLab UI:"
        echo "  1. Go to ${GITLAB_URL}/admin/runners"
        echo "  2. Click 'New instance runner'"
        echo "  3. Copy the token and set RUNNER_TOKEN env var"
    fi
}

main "$@"
