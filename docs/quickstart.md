# Quickstart Guide — 2 Minutes

Get ZK-Collector running in under 2 minutes. Choose your platform:

---

## Option 1: Docker (Fastest, Recommended)

### Prerequisites
- Docker Engine 24+
- ZKTeco device IP address on same LAN

### One-Command Deploy

```bash
docker run -d \
  --name zk-collector \
  --restart unless-stopped \
  -p 8080:8080 \
  -v zk-data:/app/data \
  -e ZK_ADMIN_PASSWORD="your-secure-password" \
  ghcr.io/nelsonelagunar/zk-collector:latest
```

### Verify It's Running

```bash
# Check container
docker ps | grep zk-collector

# Check logs
docker logs zk-collector -f

# Test health endpoint
curl http://localhost:8080/health
# → {"status":"healthy","version":"1.0.0"}
```

---

## Option 2: Raspberry Pi (Bare Metal)

### Prerequisites
- Raspberry Pi 3/4/5 with Raspberry Pi OS (64-bit)
- Python 3.12+
- ZKTeco device IP on same LAN

### Install & Run

```bash
# 1. Install system dependencies
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# 2. Clone repository
git clone https://github.com/nelsonelagunar/zk-collector.git
cd zk-collector

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install package
pip install -e .

# 5. Create config from example
cp configs/devices.example.yaml configs/devices.yaml

# 6. Edit config with your device IP
# (Use nano, vim, or your preferred editor)
nano configs/devices.yaml
```

### Edit `configs/devices.yaml` — Replace with your device IP:

```yaml
devices:
  - ip: "192.168.1.101"    # ← CHANGE THIS to your device IP
    port: 4370
    timeout: 5
    password: 0            # Default comm key (usually 0)
    name: "Main Entrance"
    enabled: true
```

### Run

```bash
# Start collector + web dashboard
zk-collector --config configs/devices.yaml
```

---

## Option 3: Docker Compose (Production-Ready)

### Create `docker-compose.yml`

```yaml
services:
  zk-collector:
    image: ghcr.io/nelsonelagunar/zk-collector:latest
    container_name: zk-collector
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - zk-data:/app/data
    environment:
      - ZK_ADMIN_PASSWORD=your-secure-password
      - CONFIG_PATH=/app/configs/devices.yaml
    # Mount your custom config (optional)
    # volumes:
    #   - ./configs/devices.yaml:/app/configs/devices.yaml:ro

volumes:
  zk-data:
```

### Deploy

```bash
docker compose up -d
```

---

## First Login & Setup

1. **Open browser** → `http://<collector-ip>:8080`
   - Local Pi: `http://localhost:8080`
   - Remote: `http://192.168.x.x:8080`

2. **First run?** You'll see the setup page:
   - Username: `admin`
   - Password: Set your secure password
   - Click **Create Admin**

3. **Already have admin?** Login with:
   - Username: `admin`
   - Password: value of `ZK_ADMIN_PASSWORD` env var

---

## Add Your First Device

1. **Navigate** to **Devices** in sidebar
2. **Click** "Add Device"
3. **Fill in**:
   ```
   Name:           Main Entrance
   Location:       Building A - Lobby
   Zone:           Zone A
   IP Address:     192.168.1.101      ← Your device IP
   Port:           4370
   Password:       0                   ← Default comm key
   Timeout:        5
   Protocol:       TCP
   ```
4. **Click** "Test Connection" → Should show ✅ Success
5. **Click** "Save"

---

## Verify Attendance Collection

1. **Wait 60 seconds** (default poll interval)
2. **Go to** Dashboard → View stats
3. **Click** "Attendance" in sidebar
4. **See** records flowing in real-time

---

## Quick Commands Reference

| Task | Command |
|------|---------|
| View logs (Docker) | `docker logs -f zk-collector` |
| View logs (Pi) | `journalctl -u zk-collector -f` |
| Stop (Docker) | `docker stop zk-collector` |
| Restart (Docker) | `docker restart zk-collector` |
| Update (Docker) | `docker pull ghcr.io/nelsonelagunar/zk-collector:latest && docker restart zk-collector` |
| Backup data (Docker) | `docker run --rm -v zk-data:/data -v $(pwd):/backup alpine tar czf /backup/zk-backup-$(date +%F).tar.gz /data` |

---

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| Can't reach web UI | Check port 8080 not blocked: `curl -v http://localhost:8080/health` |
| Device test fails | Verify device IP, port 4370, TCP/IP enabled on device |
| "Connection timeout" | Ping device from collector: `ping 192.168.1.101` |
| "Auth failed" | Device password usually `0` — check device Comm settings |
| No records showing | Wait 60s poll interval, or click "Sync Now" in dashboard |
| Forgot admin password | Delete `data/webgui.db` and restart (re-runs setup) |

---

## Next Steps

- 📖 [Full Installation Guide](installation.md) — systemd, reverse proxy, HTTPS
- 🔧 [Configuration Reference](configuration.md) — all options, env vars, YAML schema
- 📡 [API Reference](api.md) — REST endpoints for integration
- 📱 [Device Compatibility](devices.md) — tested models, firmware requirements

---

**Done!** Your ZKTeco devices are now feeding attendance to a modern web dashboard. 🎉

*Need help? Open an issue on [GitHub](https://github.com/nelsonelagunar/zk-collector/issues)*
