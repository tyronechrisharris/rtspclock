import sys
import os
import platform
import socket
import threading
import signal
import time
import numpy as np
from datetime import datetime

# Platform-specific Resource Management
if platform.system() != "Windows":
    import resource

# Platform-specific Setup for GStreamer
if platform.system() == "Windows":
    # On Windows, we often need to ensure the GStreamer bin directory is in PATH
    # so that the DLLs can be loaded by ctypes/PyGObject.
    # Typical installation path: C:\gstreamer\1.0\msvc_x86_64\bin
    gst_path = os.environ.get("GSTREAMER_1_0_ROOT_MSVC_X86_64")
    if gst_path:
        bin_path = os.path.join(gst_path, "bin")
        if os.path.exists(bin_path):
             # For Python 3.8+ on Windows, os.add_dll_directory is safer/required for ctypes
            try:
                os.add_dll_directory(bin_path)
            except AttributeError:
                pass # Python < 3.8
            # Also add to PATH for good measure
            os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]

import gi
# Ensure we check required versions before importing repositories
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib
import cv2

# Configuration
MULTICAST_GROUP = "224.0.0.1"
MULTICAST_PORT = 5400
RTSP_PORT = 8554
WIDTH = 640
HEIGHT = 480
FPS = 5

def check_port(port, host='0.0.0.0'):
    """Checks if the port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Enable SO_REUSEADDR to allow binding even if the port is in TIME_WAIT
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False

class BackendProducer:
    """
    Manages the global source pipeline.
    Generates frames with OpenCV -> appsrc -> x264enc -> udp multicast.
    """
    def __init__(self):
        self.active_clients = 0
        self.running = False
        self.thread = None

        # Pipeline: appsrc -> x264enc -> rtph264pay -> udpsink (Multicast)
        # Note: 'videoconvert' ensures format compatibility.
        # 'h264parse' and 'rtph264pay' ensure we send proper RTP packets.
        # Added buffer-size=524288 (512KB) to udpsink to reduce packet loss probability during high load
        pipeline_str = (
            f"appsrc name=source is-live=true block=true format=time do-timestamp=true "
            f"caps=video/x-raw,format=BGR,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
            f"videoconvert ! "
            f"x264enc tune=zerolatency speed-preset=ultrafast bitrate=512 ! "
            f"h264parse ! "
            f"rtph264pay config-interval=1 pt=96 ! "
            f"udpsink host={MULTICAST_GROUP} port={MULTICAST_PORT} auto-multicast=true async=false buffer-size=524288"
        )

        print(f"Backend Pipeline: {pipeline_str}")
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
        except Exception as e:
            print(f"Error parsing pipeline: {e}")
            raise

        self.appsrc = self.pipeline.get_by_name('source')

        # Start playing immediately
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Unable to start backend pipeline")

        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        """Generates frames at 5 FPS."""
        frame_duration = 1.0 / FPS

        while self.running:
            start_time = time.time()

            # 1. Create Image
            # Black background
            img = np.zeros((HEIGHT, WIDTH, 3), np.uint8)

            # 2. Add Text
            # Current time
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(img, f"Time: {now}", (50, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Active Connections
            cv2.putText(img, f"Active Clients: {self.active_clients}", (50, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # 3. Push to GStreamer
            # Convert to buffer
            data = img.tobytes()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)

            self.appsrc.emit("push-buffer", buf)

            # 4. Sleep to maintain FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_duration - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
        if self.thread:
            self.thread.join()

    def update_clients(self, count):
        self.active_clients = count

class ZeroLatencyFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, launch_str):
        super().__init__()
        self.set_launch(launch_str)
        self.set_shared(True)
        # Always-On Mode
        self.set_suspend_mode(GstRtspServer.RTSPSuspendMode.NONE)

    def do_configure(self, media):
        # Set latency to 0 for instant playback (disables jitter buffer on server side)
        # Note: GStreamer default is ~200ms.
        # For a simulator on loopback/LAN, 0 is safe and feels "instant".
        media.set_latency(0)

        # Call parent configure just in case (though Python bindings sometimes handle this oddly,
        # normally we return void or call super)
        # GstRtspServer.RTSPMediaFactory.do_configure(self, media)
        # In PyGObject, overriding vfuncs is automatic.

class RTSPServer(GstRtspServer.RTSPServer):
    def __init__(self, producer):
        super().__init__()
        self.producer = producer
        self.set_service(str(RTSP_PORT))

        mounts = self.get_mount_points()

        # Pipeline for clients:
        # Simplified: udpsrc -> rtph264depay -> rtph264pay
        # Removed h264parse for speed. Backend is already sending compliant H.264 RTP.
        # Retained depay/pay sandwich to ensure correct SSRC/SeqNum negotiation for each client
        # while sharing the backend multicast.
        launch_str = (
            f"udpsrc multicast-group={MULTICAST_GROUP} port={MULTICAST_PORT} auto-multicast=true buffer-size=524288 ! "
            f"application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=96 ! "
            f"rtph264depay ! rtph264pay name=pay0 config-interval=1 pt=96"
        )

        print(f"Client Launch String: {launch_str}")

        # Increase Thread Pool for handling simultaneous connections
        pool = GstRtspServer.RTSPThreadPool.new()
        pool.set_max_threads(200)
        self.set_thread_pool(pool)

        print("Pre-warming 100 RTSP endpoints (Always-On Mode)...")
        for i in range(1, 101):
            # Use custom factory to force 0 latency
            factory = ZeroLatencyFactory(launch_str)
            mounts.add_factory(f"/cam{i}", factory)

        # Track clients
        self.client_count = 0
        self.connect("client-connected", self.on_client_connected)

    def on_client_connected(self, server, client):
        self.client_count += 1
        self.producer.update_clients(self.client_count)
        # print(f"Client connected. Total: {self.client_count}")
        client.connect("closed", self.on_client_closed)

    def on_client_closed(self, client):
        self.client_count -= 1
        self.producer.update_clients(self.client_count)
        # print(f"Client disconnected. Total: {self.client_count}")

def increase_rlimit():
    """
    Increases the open file limit to the maximum allowed by the hard limit.
    Essential for high-concurrency servers on macOS/Linux.
    """
    if platform.system() == "Windows":
        return

    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = hard
        # macOS often reports 'infinity' as a very large number, but practically caps around 10240 without root.
        # We try to set it to at least 4096 if possible.
        if target == resource.RLIM_INFINITY:
            target = 65536 # A reasonable upper bound for user processes

        if soft < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
            print(f"Increased open file limit: {soft} -> {target}")
        else:
            print(f"Open file limit is already sufficient: {soft}")

    except Exception as e:
        print(f"Warning: Failed to increase open file limit: {e}")

def main():
    # Optimize System Resources
    increase_rlimit()

    # Initialize GStreamer
    try:
        Gst.init(None)
    except Exception as e:
        print(f"Failed to initialize GStreamer: {e}")
        print("Please ensure GStreamer is installed and the bin directory is in your PATH.")
        sys.exit(1)

    # Port Check
    if not check_port(RTSP_PORT):
        print(f"Error: Port {RTSP_PORT} is already in use.")
        sys.exit(1)

    print(f"Port {RTSP_PORT} is available.")

    # Start Backend Producer
    try:
        producer = BackendProducer()
        print(f"Backend Producer started (Multicast {MULTICAST_GROUP}:{MULTICAST_PORT}).")
    except Exception as e:
        print(f"Failed to start backend: {e}")
        sys.exit(1)

    # Start RTSP Server
    try:
        server = RTSPServer(producer)
        server.attach(None)
        print(f"RTSP Server running at rtsp://localhost:{RTSP_PORT}/cam1 ... /cam100")
    except Exception as e:
        print(f"Failed to start RTSP server: {e}")
        producer.stop()
        sys.exit(1)

    # Main Loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        producer.stop()

if __name__ == "__main__":
    main()
