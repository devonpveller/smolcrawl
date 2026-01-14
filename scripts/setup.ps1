# SmolCrawl Setup Script for Windows PowerShell
# ==============================================
# This script sets up a complete development environment

param(
    [switch]$Full,        # Install full dependencies (crawlee, tantivy)
    [switch]$Dev,         # Install development dependencies
    [switch]$SkipVenv,    # Skip virtual environment creation
    [string]$PythonPath   # Custom Python path (default: python)
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SmolCrawl Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Determine Python command
$python = if ($PythonPath) { $PythonPath } else { "python" }

# Check Python version
Write-Host "[1/5] Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = & $python --version 2>&1
    Write-Host "  Found: $pythonVersion" -ForegroundColor Green
    
    # Parse version and check >= 3.11
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Host "  ERROR: Python 3.11+ required, found $major.$minor" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Check Node.js (required for readabilipy)
Write-Host "[2/5] Checking Node.js (required for readabilipy)..." -ForegroundColor Yellow
try {
    $nodeVersion = & node --version 2>&1
    Write-Host "  Found: Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Node.js not found!" -ForegroundColor Yellow
    Write-Host "  readabilipy requires Node.js for full functionality." -ForegroundColor Yellow
    Write-Host "  Install from: https://nodejs.org/" -ForegroundColor Yellow
    Write-Host ""
}

# Create virtual environment
if (-not $SkipVenv) {
    Write-Host "[3/5] Creating virtual environment..." -ForegroundColor Yellow
    $venvPath = ".venv"
    
    if (Test-Path $venvPath) {
        Write-Host "  Virtual environment already exists at $venvPath" -ForegroundColor Green
    } else {
        & $python -m venv $venvPath
        Write-Host "  Created virtual environment at $venvPath" -ForegroundColor Green
    }
    
    # Activate virtual environment
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        . $activateScript
        Write-Host "  Activated virtual environment" -ForegroundColor Green
    }
} else {
    Write-Host "[3/5] Skipping virtual environment creation..." -ForegroundColor Yellow
}

# Upgrade pip
Write-Host "[4/5] Upgrading pip..." -ForegroundColor Yellow
& $python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host "[5/5] Installing dependencies..." -ForegroundColor Yellow

if ($Full -and $Dev) {
    Write-Host "  Installing all dependencies (core + full + dev)..." -ForegroundColor Cyan
    & $python -m pip install -e ".[full,dev]"
} elseif ($Full) {
    Write-Host "  Installing core + full dependencies..." -ForegroundColor Cyan
    & $python -m pip install -e ".[full]"
} elseif ($Dev) {
    Write-Host "  Installing core + dev dependencies..." -ForegroundColor Cyan
    & $python -m pip install -e ".[dev]"
} else {
    Write-Host "  Installing core dependencies only..." -ForegroundColor Cyan
    & $python -m pip install -e .
}

# Install Node.js dependencies (for readabilipy)
if (Test-Path "package.json") {
    Write-Host ""
    Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
    try {
        & npm install --quiet 2>$null
        Write-Host "  Node.js dependencies installed" -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: Could not install Node.js dependencies" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Activate venv:  .\.venv\Scripts\Activate.ps1"
Write-Host "  2. Run batch tool: .\smolcrawl.bat"
Write-Host "  3. Or use CLI:     python use-cases/document-processing/doc_processor.py --help"
Write-Host ""

if (-not $Full) {
    Write-Host "TIP: For full functionality (crawlee, tantivy search), run:" -ForegroundColor Yellow
    Write-Host "     .\scripts\setup.ps1 -Full" -ForegroundColor Yellow
}
