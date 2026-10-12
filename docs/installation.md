# Installation Guide

### Prerequisites
- Python 3.12+
- Network access to your ZKTeco device(s)
- (For Docker) Docker Engine 24+

### Option 1: Docker Compose (Recommended — Single Command)

```bash
# Clone and setup
git clone https://github.com/nelsonelagunar/zk-collector.git
cd zk-collector

# Copy environment template and configure
cp .env.example .env
# Edit .env to set ZK_ADMIN_PASSWORD and ENCRYPTION_KEY
# nano .env

# Deploy
docker-compose up -d
```

### Option 1b: Docker (Standalone)

```bash
# Requires both ZK_ADMIN_PASSWORD and ENCRYPTION_KEY
docker run -d \
  --name zk-collector \
  -p 8080:8080 \
  -v zk-data:/app/data \
  -e ZK_ADMIN_PASSWORD=your-secure-password \
  -e ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  ghcr.io/nelsonelagunar/zk-collector:latest
```

### Option 2: Raspberry Pi

```bash
# Install system deps
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# Clone and setup
git clone https://github.com/nelsonelagunar/zk-collector.git
cd zk-collector
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Run
zk-collector --config configs/devices.yaml
```

### Option 3: systemd Service (Production Pi)

```bash
# Copy service file
sudo deploy/zk-collector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zk-collector
```

### Network Requirements

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 8080 | TCP | Inbound | Web dashboard |
| 4370 | TCP/UDP | Outbound | ZKTeco device communication |

**Important:** Port 4370 must be accessible from the collector to each ZKTeco device on your LAN. Do NOT expose this port to the internet.
