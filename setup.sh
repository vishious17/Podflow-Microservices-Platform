#!/usr/bin/env bash

# Exit on any error
set -e

# Define colors for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=================================================${NC}"
echo -e "${BLUE}        🚀 Initializing PodFlow Setup 🚀         ${NC}"
echo -e "${CYAN}=================================================${NC}\n"

# 1. Dependency checks
echo -e "${YELLOW}➔ Checking required dependencies...${NC}"

check_dependency() {
    if command -v "$1" >/dev/null 2>&1; then
        echo -e "  [${GREEN}✓${NC}] $1 is installed"
    else
        echo -e "  [${RED}✗${NC}] $1 is missing! Please install $1 to continue."
        exit 1
    fi
}

check_dependency "podman"
check_dependency "podman-compose"
check_dependency "python3"

echo ""

# 2. Setup permissions
echo -e "${YELLOW}➔ Setting file permissions...${NC}"

if [ -d "scripts" ]; then
    chmod +x scripts/*.py
    echo -e "  [${GREEN}✓${NC}] Made Python automation scripts executable"
else
    echo -e "  [${YELLOW}!${NC}] Warning: 'scripts' directory not found"
fi

echo ""

# 3. Future-proofing: Create ignored folders if necessary
# Although mostly managed by Podman, having empty local folders ready can help
echo -e "${YELLOW}➔ Ensuring directory structure...${NC}"
if [ ! -d "volumes" ]; then
    mkdir -p volumes
    echo -e "  [${GREEN}✓${NC}] Created local 'volumes' directory"
else
    echo -e "  [${GREEN}✓${NC}] 'volumes' directory already exists"
fi

echo ""

echo -e "${CYAN}=================================================${NC}"
echo -e "${GREEN}✨ Setup Complete! ✨${NC}"
echo -e "You are ready to run PodFlow."
echo -e "\nTo start the platform, run:"
echo -e "  ${YELLOW}podman-compose up --build${NC}\n"
echo -e "To start the orchestration script in a new terminal:"
echo -e "  ${YELLOW}python3 scripts/orchestrator.py${NC}"
echo -e "${CYAN}=================================================${NC}"
