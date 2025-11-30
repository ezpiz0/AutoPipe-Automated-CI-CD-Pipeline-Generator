#!/bin/bash
# AutoPipe GitLab Runner Auto-Registration Script
# This script automatically registers the runner with GitLab

set -e

GITLAB_URL="${GITLAB_URL:-http://gitlab}"
RUNNER_TOKEN="${RUNNER_TOKEN:-}"
RUNNER_DESCRIPTION="${RUNNER_DESCRIPTION:-autopipe-runner}"
RUNNER_TAGS="${RUNNER_TAGS:-docker,autopipe}"
RUNNER_EXECUTOR="${RUNNER_EXECUTOR:-docker}"
DOCKER_IMAGE="${DOCKER_IMAGE:-docker:latest}"

echo "=========================================="
echo "AutoPipe GitLab Runner Setup"
echo "=========================================="

# Function to wait for GitLab to be ready
wait_for_gitlab() {
    echo "[INFO] Waiting for GitLab to be ready..."
    max_attempts=60
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "${GITLAB_URL}/-/health" | grep -q "200"; then
            echo "[OK] GitLab is ready!"
            return 0
        fi

        attempt=$((attempt + 1))
        echo "[INFO] Waiting for GitLab... (attempt $attempt/$max_attempts)"
        sleep 10
    done

    echo "[ERROR] GitLab did not become ready in time"
    return 1
}

# Function to check if runner is already registered
check_runner_registered() {
    if [ -f /etc/gitlab-runner/config.toml ]; then
        if grep -q "url" /etc/gitlab-runner/config.toml 2>/dev/null; then
            echo "[INFO] Runner already registered"
            return 0
        fi
    fi
    return 1
}

# Function to register runner with authentication token
register_runner() {
    echo "[INFO] Registering runner..."

    if [ -z "$RUNNER_TOKEN" ]; then
        echo "[ERROR] RUNNER_TOKEN environment variable is required!"
        echo "[INFO] To get a token:"
        echo "  1. Go to GitLab Admin -> CI/CD -> Runners"
        echo "  2. Click 'New instance runner'"
        echo "  3. Copy the authentication token"
        echo "[INFO] Then set: RUNNER_TOKEN=glrt-xxxxxxxxxxxx"
        return 1
    fi

    # GitLab 15.6+ uses authentication tokens (glrt-...)
    gitlab-runner register \
        --non-interactive \
        --url "${GITLAB_URL}" \
        --token "${RUNNER_TOKEN}" \
        --executor "${RUNNER_EXECUTOR}" \
        --docker-image "${DOCKER_IMAGE}" \
        --docker-privileged \
        --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
        --docker-network-mode "autopipe-net" \
        --description "${RUNNER_DESCRIPTION}" \
        --tag-list "${RUNNER_TAGS}"

    echo "[OK] Runner registered successfully!"
}

# Main logic
main() {
    # Wait for GitLab
    wait_for_gitlab

    # Check if already registered
    if ! check_runner_registered; then
        register_runner
    fi

    echo "[INFO] Starting GitLab Runner..."
    exec gitlab-runner run --user=gitlab-runner --working-directory=/home/gitlab-runner
}

main "$@"
