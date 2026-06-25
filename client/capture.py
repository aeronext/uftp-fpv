#!/usr/bin/env python3
import cv2
import signal
import subprocess
import time
import os
import sys
from datetime import datetime, timezone

IMAGE_DIR = '/tmp/capture'
UFTP_SERVER = os.environ.get('UFTP_SERVER', '192.168.1.100')
FPS = float(os.environ.get('FPS', '1'))
CAMERA_INDEX = int(os.environ.get('CAMERA_INDEX', '0'))
JPEG_QUALITY  = int(os.environ.get('JPEG_QUALITY', '85'))
CAPTURE_WIDTH  = int(os.environ.get('CAPTURE_WIDTH', '0'))   # 0 = camera default
CAPTURE_HEIGHT = int(os.environ.get('CAPTURE_HEIGHT', '0'))  # 0 = camera default
UFTP_RECEIVER_ID = os.environ.get('UFTP_RECEIVER_ID', '')
UFTP_SENDER_ID   = os.environ.get('UFTP_SENDER_ID', '')
UFTP_RATE        = os.environ.get('UFTP_RATE', '')   # Kbps; unset = uftp default
if not UFTP_RECEIVER_ID:
    print('WARNING: UFTP_RECEIVER_ID is not set. '
          'Run "sudo journalctl -u uftp-fpv-receiver | grep UID" on the server '
          'to find the receiver UID (e.g. 0x0A920002).', file=sys.stderr)
_uftp_opts_env = os.environ.get('UFTP_OPTS', '')
_h_opts = ['-H', UFTP_RECEIVER_ID] if UFTP_RECEIVER_ID else []
_u_opts = ['-U', UFTP_SENDER_ID]   if UFTP_SENDER_ID   else []
_r_opts = ['-R', UFTP_RATE]        if UFTP_RATE        else []
UFTP_EXTRA_OPTS = ['-q'] + _h_opts + _u_opts + _r_opts + (_uftp_opts_env.split() if _uftp_opts_env else [])

os.makedirs(IMAGE_DIR, exist_ok=True)


def send_via_uftp(filepath: str) -> bool:
    cmd = ['uftp'] + UFTP_EXTRA_OPTS + ['-M', UFTP_SERVER, filepath]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f'[uftp error] {result.stderr.strip()}', file=sys.stderr)
        return False
    return True


def main():
    running = True

    def _handle_sigterm(signum, frame_):
        nonlocal running
        print('SIGTERM received, shutting down...', flush=True)
        running = False

    signal.signal(signal.SIGTERM, _handle_sigterm)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f'Cannot open camera index {CAMERA_INDEX}', file=sys.stderr)
        sys.exit(1)

    try:
        native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        save_w = CAPTURE_WIDTH  or native_w
        save_h = CAPTURE_HEIGHT or native_h
        print(f'Camera opened. Native: {native_w}x{native_h}, '
              f'Save: {save_w}x{save_h}, '
              f'Sending to {UFTP_SERVER} at {FPS} FPS', flush=True)
        interval = 1.0 / FPS

        while running:
            loop_start = time.monotonic()

            ret, frame = cap.read()
            if not ret:
                print('Failed to read frame, retrying...', file=sys.stderr)
                time.sleep(1)
                continue

            if save_w != native_w or save_h != native_h:
                frame = cv2.resize(frame, (save_w, save_h), interpolation=cv2.INTER_AREA)

            ok_enc, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if not ok_enc:
                print('Failed to encode frame, skipping.', file=sys.stderr)
                continue

            # Filename encodes UTC timestamp for chronological sorting
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
            filepath = os.path.join(IMAGE_DIR, f'camera_{ts}.jpg')
            with open(filepath, 'wb') as f:
                f.write(buf.tobytes())
                f.flush()
                os.fsync(f.fileno())

            ok = send_via_uftp(filepath)
            print(f'[{"OK" if ok else "NG"}] {os.path.basename(filepath)}', flush=True)

            try:
                os.remove(filepath)
            except OSError:
                pass

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, interval - elapsed))
    finally:
        cap.release()
        print('Camera released.', flush=True)


if __name__ == '__main__':
    main()
