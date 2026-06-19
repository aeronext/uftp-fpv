#!/usr/bin/env python3
import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, send_from_directory

app = Flask(__name__)

IMAGE_DIR = os.environ.get('IMAGE_DIR', '/data/images')
MAX_HISTORY = int(os.environ.get('MAX_HISTORY', '20'))

# Matches filenames written by capture.py: camera_YYYYMMDD_HHMMSS_ffffff.jpg
_FNAME_RE = re.compile(r'^camera_(\d{8})_(\d{6})_(\d+)\.jpg$')


def _parse_file(name: str) -> dict | None:
    m = _FNAME_RE.match(name)
    if not m:
        return None
    try:
        dt = datetime.strptime(f'{m.group(1)}_{m.group(2)}', '%Y%m%d_%H%M%S')
        dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return {
        'filename': name,
        'dt': dt,
        'display': dt.strftime('%Y-%m-%d %H:%M:%S UTC'),
        'iso': dt.isoformat(),
    }


def list_images() -> list[dict]:
    try:
        names = os.listdir(IMAGE_DIR)
    except FileNotFoundError:
        return []
    parsed = [p for n in names if (p := _parse_file(n)) is not None]
    parsed.sort(key=lambda x: x['dt'], reverse=True)
    return parsed


@app.route('/')
def index():
    images = list_images()
    latest = images[0] if images else None
    history = images[1:MAX_HISTORY] if len(images) > 1 else []
    return render_template('index.html', latest=latest, history=history)


@app.route('/api/latest')
def api_latest():
    images = list_images()
    if images:
        img = images[0]
        return jsonify({
            'filename': img['filename'],
            'datetime': img['display'],
            'iso': img['iso'],
            'total': len(images),
        })
    return jsonify({'filename': None, 'datetime': None, 'iso': None, 'total': 0})


@app.route('/images/<path:filename>')
def serve_image(filename: str):
    return send_from_directory(IMAGE_DIR, filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, threaded=True)
