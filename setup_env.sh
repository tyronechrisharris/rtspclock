#!/bin/bash
set -e

# setup_env.sh - Environment Setup for RTSP Simulator V2

echo "Starting environment setup..."

# 1. Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is not installed. Please install it first."
    exit 1
fi

echo "Updating Homebrew..."
brew update

# 2. Install GStreamer dependencies
echo "Installing GStreamer dependencies..."
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav gst-rtsp-server

# 3. Install Python 3.11 (if not present)
echo "Ensuring Python 3.11 is installed..."
brew install python@3.11

# 4. Create Virtual Environment
VENV_DIR="venv"
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists."
else
    echo "Creating virtual environment in $VENV_DIR..."
    python3.11 -m venv $VENV_DIR
fi

# 5. Activate and Install Python Requirements
source $VENV_DIR/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install pygobject opencv-python

# 6. Verify Installation
echo "Verifying GStreamer Python bindings..."
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('GStreamer bindings working.')"
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"

echo "Setup complete! Activate the environment with: source venv/bin/activate"
