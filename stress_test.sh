#!/bin/bash

# stress_test.sh - Spawn 100 RTSP clients
# Usage: ./stress_test.sh [server_ip] (default: localhost)

HOST="${1:-localhost}"
PORT=8554
COUNT=100

echo "Starting stress test against $HOST:$PORT with $COUNT clients..."

# Ensure ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed."
    exit 1
fi

pids=()

trap "echo 'Stopping all clients...'; kill ${pids[*]}; exit" SIGINT SIGTERM

for i in $(seq 1 $COUNT); do
    URL="rtsp://$HOST:$PORT/cam$i"
    echo "Starting client $i on $URL..."

    # -vcodec copy: No decoding (save CPU)
    # -f null -: Discard output
    # -rtsp_transport tcp: Force TCP interleaved (standard for stable RTSP)
    ffmpeg -rtsp_transport tcp -i "$URL" -vcodec copy -f null - > /dev/null 2>&1 &

    pids+=($!)

    # Slight stagger to avoid thundering herd on startup (optional)
    # sleep 0.1
done

echo "All $COUNT clients started. Press Ctrl+C to stop."
wait
