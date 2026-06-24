#!/usr/bin/env python3
import cv2
import subprocess
import time
import os
import sys
from datetime import datetime, timezone

IMAGE_DIR = '/tmp/capture'
UFTP_SERVER = os.environ.get('UFTP_SERVER', '192.168.1.100')
FPS = float(os.environ.get('FPS', '1'))
CAMERA_INDEX = int(os.environ.get('CAMERA_INDEX', '0'))
JPEG_QUALITY = int(os.environ.get('JPEG_QUALITY', '85'))
UFTP_RECEIVER_ID = os.environ.get('UFTP_RECEIVER_ID', '')
_base_opts = ['-q']
if UFTP_RECEIVER_ID:
    _base_opts += ['-H', UFTP_RECEIVER_ID]
_uftp_opts_env = os.environ.get('UFTP_OPTS', '')
UFTP_EXTRA_OPTS = _base_opts + (_uftp_opts_env.split() if _uftp_opts_env else [])

os.makedirs(IMAGE_DIR, exist_ok=True)


def send_via_uftp(filepath: str) -> bool:
    cmd = ['uftp'] + UFTP_EXTRA_OPTS + ['-M', UFTP_SERVER, filepath]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f'[uftp error] {result.stderr.strip()}', file=sys.stderr)
        return False
    return True


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f'Cannot open camera index {CAMERA_INDEX}', file=sys.stderr)
        sys.exit(1)

    print(f'Camera opened. Sending to {UFTP_SERVER} at {FPS} FPS', flush=True)
    interval = 1.0 / FPS

    while True:
        loop_start = time.monotonic()

        ret, frame = cap.read()
        if not ret:
            print('Failed to read frame, retrying...', file=sys.stderr)
            time.sleep(1)
            continue

        # Filename encodes UTC timestamp for chronological sorting
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        filepath = os.path.join(IMAGE_DIR, f'camera_{ts}.jpg')
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

        ok = send_via_uftp(filepath)
        print(f'[{"OK" if ok else "NG"}] {os.path.basename(filepath)}', flush=True)

        try:
            os.remove(filepath)
        except OSError:
            pass

        elapsed = time.monotonic() - loop_start
        time.sleep(max(0.0, interval - elapsed))


if __name__ == '__main__':
    main()
