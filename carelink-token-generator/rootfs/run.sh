#!/usr/bin/env bash
set -e

echo "Starting Carelink Token Generator..."

# Start virtual display for Firefox
echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Wait for display to be ready
sleep 2

# Start x11vnc server
echo "Starting VNC server..."
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 &
sleep 1

# Start noVNC websocket proxy
echo "Starting noVNC..."
websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "VNC available at port 6080"

# Start the Flask web server
echo "Starting web server on port 8099..."
cd /app
exec python3 server.py
