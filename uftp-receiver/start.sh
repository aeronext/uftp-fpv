#!/bin/sh
set -e

DEST_DIR="${DEST_DIR:-/data/images}"
LOG_FILE="${LOG_FILE:-/var/log/uftpd.log}"
PORT="${UFTP_PORT:-1044}"
MAX_IMAGES="${MAX_IMAGES:-500}"

mkdir -p "$DEST_DIR"
touch "$LOG_FILE"

# Periodically remove oldest images to stay within MAX_IMAGES
cleanup() {
    while true; do
        count=$(find "$DEST_DIR" -maxdepth 1 -name 'camera_*.jpg' | wc -l)
        if [ "$count" -gt "$MAX_IMAGES" ]; then
            excess=$((count - MAX_IMAGES))
            find "$DEST_DIR" -maxdepth 1 -name 'camera_*.jpg' \
                | sort | head -n "$excess" \
                | xargs rm -f
        fi
        sleep 10
    done
}
cleanup &

# uftpd always daemonizes (forks to background), so we can't use exec directly.
# Start it, then stream its log to stdout and monitor the process.
uftpd -D "$DEST_DIR" -L "$LOG_FILE" -p "$PORT"

tail -f "$LOG_FILE" &

# Exit with failure when uftpd dies so systemd Restart=on-failure triggers.
while pgrep -x uftpd > /dev/null; do
    sleep 5
done
echo "uftpd exited unexpectedly" >&2
exit 1
