# RTSP Simulator V2

A high-performance synthetic camera simulator designed for macOS (Apple Silicon). It simulates 100 concurrent RTSP streams to stress-test downstream security platforms.

## Features

*   **Stability First:** Uses software encoding (`x264enc`) and a robust shared pipeline architecture to prevent negotiation errors and segmentation faults.
*   **High Efficiency:** Generates and encodes the video frame **ONCE**, then multicasts it internally to serve 100 distinct RTSP mount points.
*   **Dynamic Overlay:** Generates synthetic 640x480 @ 5FPS video with current time and active client count overlays.
*   **Persistence:** The video pipeline starts immediately and stays running regardless of client connections.

## Prerequisites

*   macOS (Apple Silicon recommended for performance)
*   Homebrew installed

## Installation

1.  **Run the setup script:**
    This script will install all required GStreamer dependencies via Homebrew, create a Python virtual environment, and install Python requirements.
    ```bash
    ./setup_env.sh
    ```

2.  **Activate the environment:**
    ```bash
    source venv/bin/activate
    ```

## Usage

### 1. Start the Server

Run the main Python script. It will check if port **8554** is available and start serving.

```bash
python rtsp_sim_v2.py
```

*   **RTSP URL:** `rtsp://localhost:8554/cam1` ... `rtsp://localhost:8554/cam100`
*   **Multicast Backend:** Internally uses `224.0.0.1:5400`.

### 2. Run Stress Test

To simulate 100 concurrent clients connecting to the server:

```bash
./stress_test.sh
```

This script spawns 100 `ffmpeg` processes that consume the stream without decoding it (saving client-side CPU).

## Architecture Details

*   **Backend Producer:** A singleton class that runs an OpenCV -> `appsrc` -> `x264enc` -> `udpsink` pipeline. It broadcasts the H.264 stream to a local UDP multicast group.
*   **RTSP Server:** Configured with 100 mount points. Each mount point uses a `udpsrc` pipeline to listen to the multicast group. This ensures that the heavy lifting (encoding) happens only once, regardless of how many clients are connected.
