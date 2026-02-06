#!/bin/bash
#
# start_watcher.sh - Start the Gmail Inbox Helper menu bar watcher
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if already running
if [ -f watcher.pid ]; then
    PID=$(cat watcher.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Gmail watcher is already running with PID $PID"
        exit 0
    else
        echo "Stale PID file found, cleaning up..."
        rm watcher.pid
    fi
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Start watcher
echo "Starting Gmail Inbox Helper watcher..."
source venv/bin/activate
nohup python3 gmail_watcher.py > /dev/null 2>&1 &
PID=$!
echo $PID > watcher.pid

# Verify startup
sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "✓ Gmail watcher started with PID $PID"
    echo "  Look for 📬 icon in your menu bar"
    echo "  Logs: watcher.log"
    echo "  To stop: ./stop_watcher.sh"
else
    echo "✗ Gmail watcher failed to start. Check watcher.log"
    rm -f watcher.pid
    exit 1
fi
