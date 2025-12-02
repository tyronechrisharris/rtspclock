# setup_env.ps1 - Environment Setup for RTSP Simulator V2 (Windows)

Write-Host "Starting environment setup for Windows..." -ForegroundColor Cyan

# 1. Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from python.org or the Microsoft Store."
    exit 1
}

# 2. Check for GStreamer
$env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = [System.Environment]::GetEnvironmentVariable("GSTREAMER_1_0_ROOT_MSVC_X86_64", [System.EnvironmentVariableTarget]::User)
if (-not $env:GSTREAMER_1_0_ROOT_MSVC_X86_64) {
    # Try checking machine scope
    $env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = [System.Environment]::GetEnvironmentVariable("GSTREAMER_1_0_ROOT_MSVC_X86_64", [System.EnvironmentVariableTarget]::Machine)
}

if (-not $env:GSTREAMER_1_0_ROOT_MSVC_X86_64) {
    Write-Host "Warning: GStreamer environment variable GSTREAMER_1_0_ROOT_MSVC_X86_64 not found." -ForegroundColor Yellow
    Write-Host "Please ensure you have installed GStreamer (MSVC 64-bit) from:" -ForegroundColor Yellow
    Write-Host "https://gstreamer.freedesktop.org/download/" -ForegroundColor Yellow
    Write-Host "You need BOTH the 'runtime' and 'development' installers." -ForegroundColor Yellow
} else {
    Write-Host "GStreamer found at: $env:GSTREAMER_1_0_ROOT_MSVC_X86_64" -ForegroundColor Green

    # Check for pkg-config (needed for building pygobject sometimes, though binary wheels usually work now)
    # Actually, on Windows, pip install pygobject usually pulls binary wheels that work if GStreamer is in PATH.
}

# 3. Create Virtual Environment
$VENV_DIR = "venv"
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating virtual environment in $VENV_DIR..." -ForegroundColor Cyan
    python -m venv $VENV_DIR
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Cyan
}

# 4. Install Dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
# Activate venv for the installation step
& ".\$VENV_DIR\Scripts\python" -m pip install --upgrade pip
& ".\$VENV_DIR\Scripts\python" -m pip install pygobject opencv-python

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "To activate the environment, run: .\venv\Scripts\Activate.ps1"
