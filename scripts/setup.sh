#!/bin/bash
# SmolCrawl Setup Script for Linux/macOS
# =======================================
# This script sets up a complete development environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
FULL=false
DEV=false
SKIP_VENV=false
PYTHON_CMD="python3"

while [[ $# -gt 0 ]]; do
    case $1 in
        --full) FULL=true; shift ;;
        --dev) DEV=true; shift ;;
        --skip-venv) SKIP_VENV=true; shift ;;
        --python) PYTHON_CMD="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}========================================"
echo "  SmolCrawl Environment Setup"
echo -e "========================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}[1/5] Checking Python version...${NC}"
if command -v $PYTHON_CMD &> /dev/null; then
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
    echo -e "  ${GREEN}Found: $PYTHON_VERSION${NC}"
    
    # Parse and check version >= 3.11
    VERSION_NUM=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJOR=$(echo $VERSION_NUM | cut -d. -f1)
    MINOR=$(echo $VERSION_NUM | cut -d. -f2)
    
    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
        echo -e "  ${RED}ERROR: Python 3.11+ required, found $MAJOR.$MINOR${NC}"
        exit 1
    fi
else
    echo -e "  ${RED}ERROR: Python not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Check Node.js (required for readabilipy)
echo -e "${YELLOW}[2/5] Checking Node.js (required for readabilipy)...${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "  ${GREEN}Found: Node.js $NODE_VERSION${NC}"
else
    echo -e "  ${YELLOW}WARNING: Node.js not found!${NC}"
    echo -e "  readabilipy requires Node.js for full functionality."
    echo -e "  Install from: https://nodejs.org/"
    echo ""
fi

# Create virtual environment
if [ "$SKIP_VENV" = false ]; then
    echo -e "${YELLOW}[3/5] Creating virtual environment...${NC}"
    VENV_PATH=".venv"
    
    if [ -d "$VENV_PATH" ]; then
        echo -e "  ${GREEN}Virtual environment already exists at $VENV_PATH${NC}"
    else
        $PYTHON_CMD -m venv $VENV_PATH
        echo -e "  ${GREEN}Created virtual environment at $VENV_PATH${NC}"
    fi
    
    # Activate virtual environment
    source "$VENV_PATH/bin/activate"
    echo -e "  ${GREEN}Activated virtual environment${NC}"
else
    echo -e "${YELLOW}[3/5] Skipping virtual environment creation...${NC}"
fi

# Upgrade pip
echo -e "${YELLOW}[4/5] Upgrading pip...${NC}"
$PYTHON_CMD -m pip install --upgrade pip --quiet

# Install dependencies
echo -e "${YELLOW}[5/5] Installing dependencies...${NC}"

if [ "$FULL" = true ] && [ "$DEV" = true ]; then
    echo -e "  ${CYAN}Installing all dependencies (core + full + dev)...${NC}"
    $PYTHON_CMD -m pip install -e ".[full,dev]"
elif [ "$FULL" = true ]; then
    echo -e "  ${CYAN}Installing core + full dependencies...${NC}"
    $PYTHON_CMD -m pip install -e ".[full]"
elif [ "$DEV" = true ]; then
    echo -e "  ${CYAN}Installing core + dev dependencies...${NC}"
    $PYTHON_CMD -m pip install -e ".[dev]"
else
    echo -e "  ${CYAN}Installing core dependencies only...${NC}"
    $PYTHON_CMD -m pip install -e .
fi

# Install Node.js dependencies (for readabilipy)
if [ -f "package.json" ]; then
    echo ""
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    if command -v npm &> /dev/null; then
        npm install --quiet 2>/dev/null || true
        echo -e "  ${GREEN}Node.js dependencies installed${NC}"
    else
        echo -e "  ${YELLOW}WARNING: npm not found, skipping Node.js dependencies${NC}"
    fi
fi

echo ""
echo -e "${GREEN}========================================"
echo "  Setup Complete!"
echo -e "========================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Activate venv:  source .venv/bin/activate"
echo "  2. Run CLI:        python use-cases/document-processing/doc_processor.py --help"
echo ""

if [ "$FULL" = false ]; then
    echo -e "${YELLOW}TIP: For full functionality (crawlee, tantivy search), run:${NC}"
    echo "     ./scripts/setup.sh --full"
fi
