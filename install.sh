#!/bin/bash
# AutoPipe - Installation Script for Linux/macOS
# Команда 43 - T1 Challenge 2025

set -e

echo "=========================================="
echo "AutoPipe - CI/CD Pipeline Generator"
echo "Installation Script for Linux/macOS"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v apt-get &> /dev/null; then
            PKG_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            PKG_MANAGER="yum"
        elif command -v dnf &> /dev/null; then
            PKG_MANAGER="dnf"
        elif command -v pacman &> /dev/null; then
            PKG_MANAGER="pacman"
        else
            PKG_MANAGER="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG_MANAGER="brew"
    else
        error "Unsupported OS: $OSTYPE"
    fi
    info "Detected OS: $OS (Package manager: $PKG_MANAGER)"
}

# Check and install Python
install_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        info "Python already installed: $PYTHON_VERSION"
    else
        warn "Python not found. Installing..."
        case $PKG_MANAGER in
            apt)
                sudo apt-get update
                sudo apt-get install -y python3 python3-pip python3-venv
                ;;
            yum|dnf)
                sudo $PKG_MANAGER install -y python3 python3-pip
                ;;
            pacman)
                sudo pacman -S --noconfirm python python-pip
                ;;
            brew)
                brew install python3
                ;;
            *)
                error "Please install Python 3.9+ manually"
                ;;
        esac
        info "Python installed successfully"
    fi
}

# Check and install Docker
install_docker() {
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version 2>&1 | cut -d' ' -f3 | tr -d ',')
        info "Docker already installed: $DOCKER_VERSION"
    else
        warn "Docker not found. Installing..."
        case $OS in
            linux)
                curl -fsSL https://get.docker.com -o get-docker.sh
                sudo sh get-docker.sh
                sudo usermod -aG docker $USER
                rm get-docker.sh
                info "Docker installed. Please log out and log back in for group changes to take effect."
                ;;
            macos)
                if command -v brew &> /dev/null; then
                    brew install --cask docker
                    info "Docker Desktop installed. Please start Docker Desktop from Applications."
                else
                    warn "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
                fi
                ;;
        esac
    fi
}

# Check and install Docker Compose
install_docker_compose() {
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
        info "Docker Compose already installed"
    else
        warn "Docker Compose not found. Installing..."
        case $OS in
            linux)
                sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
                sudo chmod +x /usr/local/bin/docker-compose
                ;;
            macos)
                # Docker Compose is included with Docker Desktop
                warn "Docker Compose is included with Docker Desktop"
                ;;
        esac
    fi
}

# Check and install Git
install_git() {
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version 2>&1 | cut -d' ' -f3)
        info "Git already installed: $GIT_VERSION"
    else
        warn "Git not found. Installing..."
        case $PKG_MANAGER in
            apt)
                sudo apt-get install -y git
                ;;
            yum|dnf)
                sudo $PKG_MANAGER install -y git
                ;;
            pacman)
                sudo pacman -S --noconfirm git
                ;;
            brew)
                brew install git
                ;;
        esac
    fi
}

# Install Python dependencies
install_python_deps() {
    info "Installing Python dependencies..."

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip

    # Install from pyproject.toml
    pip install -e .

    info "Python dependencies installed successfully"
}

# Main installation
main() {
    echo ""
    info "Starting installation..."
    echo ""

    detect_os
    echo ""

    info "Step 1/5: Checking Python..."
    install_python
    echo ""

    info "Step 2/5: Checking Git..."
    install_git
    echo ""

    info "Step 3/5: Checking Docker..."
    install_docker
    echo ""

    info "Step 4/5: Checking Docker Compose..."
    install_docker_compose
    echo ""

    info "Step 5/5: Installing Python dependencies..."
    install_python_deps
    echo ""

    echo "=========================================="
    echo -e "${GREEN}Installation completed!${NC}"
    echo "=========================================="
    echo ""
    echo "To start CI/CD infrastructure:"
    echo "  docker-compose up -d"
    echo ""
    echo "To use AutoPipe:"
    echo "  source venv/bin/activate"
    echo "  python -m autopipe analyze <repo_url>"
    echo "  python -m autopipe generate <repo_url> -o output/"
    echo ""
    echo "For full documentation, see README.md"
    echo ""
}

main "$@"
