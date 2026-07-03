#!/usr/bin/env bash
set -e

echo "================================================="
echo "         PodFlow Setup"
echo "================================================="
echo ""

check_dependency() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "  [OK] $1 is installed"
    else
        echo "  [MISSING] $1 not found. Please install it to continue."
        exit 1
    fi
}

echo "Checking dependencies..."
check_dependency "podman"
check_dependency "podman-compose"
check_dependency "python3"
echo ""

echo "Setting file permissions..."
if [ -d "scripts" ]; then
    chmod +x scripts/*.py
    echo "  [OK] Scripts made executable"
else
    echo "  [WARN] scripts/ directory not found"
fi
echo ""

echo "Ensuring directory structure..."
mkdir -p volumes
echo "  [OK] volumes/ directory ready"
echo ""

echo "================================================="
echo "Setup complete."
echo ""
echo "To start PodFlow:"
echo "  podman-compose up --build"
echo ""
echo "To start the orchestrator (in a separate terminal):"
echo "  python3 scripts/orchestrator.py"
echo "================================================="
