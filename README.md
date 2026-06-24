# UFTP FPV Camera System

3-container system that streams FPV camera frames from a drone to a web viewer via UFTP.

```
[drone / client]  --UFTP UDP--> [receiver]  --shared volume--> [web-viewer]
```

## Containers

| Container | Image | Role |
|---|---|---|
| `uftp-fpv-client` | `ghcr.io/aeronext/uftp-fpv-client` | Captures camera frames and sends via UFTP |
| `uftp-fpv-receiver` | `ghcr.io/aeronext/uftp-fpv-receiver` | Receives frames over UDP and writes to shared volume |
| `uftp-fpv-web` | `ghcr.io/aeronext/uftp-fpv-web` | Flask web viewer serving latest frame at `:5000` |

## Deploy to GCP (GCE + Podman Quadlet)

The receiver and web-viewer run on a GCE VM as systemd services managed by Podman Quadlet.

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- GCP project configured

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 1. Create VM

```bash
gcloud compute instances create uftp-fpv-server \
  --zone=asia-northeast1-b \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=uftp-fpv
```

### 2. Firewall rules

```bash
gcloud compute firewall-rules create allow-fpv-web \
  --allow=tcp:5000 \
  --target-tags=uftp-fpv \
  --description="FPV web viewer"

gcloud compute firewall-rules create allow-uftp \
  --allow=udp:1044 \
  --target-tags=uftp-fpv \
  --description="UFTP receiver"
```

### 3. Install Podman

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b \
  --command="sudo apt-get update && sudo apt-get install -y podman"
```

### 4. Copy Quadlet files

Run from the project root:

```bash
gcloud compute scp \
  systemd/fpv-images.volume \
  systemd/uftp-fpv-receiver.container \
  systemd/uftp-fpv-web.container \
  uftp-fpv-server:/tmp/ \
  --zone=asia-northeast1-b
```

### 5. Place files and start services

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo mv /tmp/fpv-images.volume \
          /tmp/uftp-fpv-receiver.container \
          /tmp/uftp-fpv-web.container \
          /etc/containers/systemd/

  sudo systemctl daemon-reload

  sudo systemctl enable --now uftp-fpv-receiver
  sudo systemctl enable --now uftp-fpv-web
"
```

### 6. Get external IP and verify

```bash
gcloud compute instances describe uftp-fpv-server \
  --zone=asia-northeast1-b \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Open `http://<EXTERNAL_IP>:5000` in a browser.

### Logs and troubleshooting

```bash
# Service status
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo systemctl status uftp-fpv-receiver
  sudo systemctl status uftp-fpv-web
"

# Follow logs
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo journalctl -u uftp-fpv-web -f
"

# Running containers
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo podman ps
"
```

## Updating images

When a new image is pushed to GHCR, pull and restart on the VM:

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo podman pull ghcr.io/aeronext/uftp-fpv-receiver:latest
  sudo podman pull ghcr.io/aeronext/uftp-fpv-web:latest
  sudo systemctl restart uftp-fpv-receiver uftp-fpv-web
"
```

## Local development (Podman Quadlet)

Copy the files from `systemd/` to `~/.config/containers/systemd/` for rootless operation:

```bash
cp systemd/*.container systemd/*.volume ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start uftp-fpv-receiver uftp-fpv-web
```

## Configuration

| Service | Variable | Default | Description |
|---|---|---|---|
| receiver | `DEST_DIR` | `/data/images` | Directory to write received images |
| receiver | `UFTP_PORT` | `1044` | UDP port to listen on |
| receiver | `MAX_IMAGES` | `500` | Maximum images to retain |
| web | `IMAGE_DIR` | `/data/images` | Directory to read images from |
| web | `MAX_HISTORY` | `20` | Number of history thumbnails shown |
| web | `PORT` | `5000` | HTTP port |
| client | `UFTP_SERVER` | — | IP address of the receiver VM |
| client | `FPS` | `2` | Capture frames per second |
| client | `JPEG_QUALITY` | `80` | JPEG quality (1–100) |
