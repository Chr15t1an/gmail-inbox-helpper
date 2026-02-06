#!/bin/bash
#
# stop_watcher.sh - Stop the Gmail Inbox Helper menu bar watcher
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f watcher.pid ]; then
    PID=$(cat watcher.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping Gmail watcher (PID $PID)..."
        kill "$PID"
        sleep 1

        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force killing..."
            kill -9 "$PID" 2>/dev/null
        fi

        rm watcher.pid
        echo "✓ Gmail watcher stopped"
    else
        echo "Gmail watcher process not running (stale PID file)"
        rm watcher.pid
    fi
else
    # Try to find and kill by process name
    PIDS=$(pgrep -f "python.*gmail_watcher.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "Found Gmail watcher process(es): $PIDS"
        echo "Stopping..."
        kill $PIDS 2>/dev/null
        echo "✓ Gmail watcher stopped"
    else
        echo "Gmail watcher is not running"
    fi
fi
