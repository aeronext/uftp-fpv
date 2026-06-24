# UFTP FPV カメラシステム

ドローンのカメラ映像をUFTP経由でWebビューアに転送する3コンテナ構成のシステムです。

```
[ドローン / client]  --UFTP UDP--> [receiver]  --共有ボリューム--> [web-viewer]
```

## コンテナ構成

| コンテナ | イメージ | 役割 |
|---|---|---|
| `uftp-fpv-client` | `ghcr.io/aeronext/uftp-fpv-client` | カメラフレームをキャプチャしてUFTP送信 |
| `uftp-fpv-receiver` | `ghcr.io/aeronext/uftp-fpv-receiver` | UDPでフレームを受信して共有ボリュームに書き込み |
| `uftp-fpv-web` | `ghcr.io/aeronext/uftp-fpv-web` | 最新フレームをWebで表示（`:5000`） |

## GCPへのデプロイ（GCE + Podman Quadlet）

receiverとweb-viewerはGCE VMでPodman Quadletによるsystemdサービスとして動作します。

### 前提条件

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) がインストール済みでログイン済みであること
- GCPプロジェクトが設定済みであること

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 1. VMの作成

```bash
gcloud compute instances create uftp-fpv-server \
  --zone=asia-northeast1-b \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=uftp-fpv
```

### 2. ファイアウォールの設定

```bash
gcloud compute firewall-rules create allow-fpv-web \
  --allow=tcp:5000 \
  --target-tags=uftp-fpv \
  --description="FPV Webビューア"

gcloud compute firewall-rules create allow-uftp \
  --allow=udp:1044 \
  --target-tags=uftp-fpv \
  --description="UFTPレシーバー"
```

### 3. Podmanのインストール

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b \
  --command="sudo apt-get update && sudo apt-get install -y podman"
```

### 4. Quadletファイルのコピー

プロジェクトルートから実行してください：

```bash
gcloud compute scp \
  systemd/fpv-images.volume \
  systemd/uftp-fpv-receiver.container \
  systemd/uftp-fpv-web.container \
  uftp-fpv-server:/tmp/ \
  --zone=asia-northeast1-b
```

### 5. ファイルを配置してサービスを起動

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo mv /tmp/fpv-images.volume \
          /tmp/uftp-fpv-receiver.container \
          /tmp/uftp-fpv-web.container \
          /etc/containers/systemd/

  sudo systemctl daemon-reload

  # Quadlet生成ユニットはenableではなくstartで起動（自動起動はQuadletが管理）
  sudo systemctl start uftp-fpv-receiver
  sudo systemctl start uftp-fpv-web
"
```

### 6. 外部IPの確認とアクセス

```bash
gcloud compute instances describe uftp-fpv-server \
  --zone=asia-northeast1-b \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

ブラウザで `http://<外部IP>:5000` を開くとWebビューアが表示されます。

### ログ確認・トラブルシュート

```bash
# サービスの状態確認
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo systemctl status uftp-fpv-receiver
  sudo systemctl status uftp-fpv-web
"

# ログのリアルタイム確認
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo journalctl -u uftp-fpv-web -f
"

# 実行中コンテナの確認
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo podman ps
"
```

## イメージの更新

GHCRに新しいイメージがpushされた場合は、VM上で以下を実行してください：

```bash
gcloud compute ssh uftp-fpv-server --zone=asia-northeast1-b --command="
  sudo podman pull ghcr.io/aeronext/uftp-fpv-receiver:latest
  sudo podman pull ghcr.io/aeronext/uftp-fpv-web:latest
  sudo systemctl restart uftp-fpv-receiver uftp-fpv-web
"
```

## ローカル開発（Podman Quadlet）

rootlessで動作させる場合は `~/.config/containers/systemd/` にファイルをコピーしてください：

```bash
cp systemd/*.container systemd/*.volume ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start uftp-fpv-receiver uftp-fpv-web
```

## 環境変数

| サービス | 変数名 | デフォルト値 | 説明 |
|---|---|---|---|
| receiver | `DEST_DIR` | `/data/images` | 受信画像の保存先ディレクトリ |
| receiver | `UFTP_PORT` | `1044` | 待受UDPポート番号 |
| receiver | `MAX_IMAGES` | `500` | 保持する画像の最大枚数 |
| web | `IMAGE_DIR` | `/data/images` | 画像の読み込み元ディレクトリ |
| web | `MAX_HISTORY` | `20` | 履歴サムネイルの表示枚数 |
| web | `PORT` | `5000` | HTTPポート番号 |
| client | `UFTP_SERVER` | — | receiverのIPアドレス |
| client | `FPS` | `2` | キャプチャフレームレート |
| client | `JPEG_QUALITY` | `80` | JPEG品質（1〜100） |
