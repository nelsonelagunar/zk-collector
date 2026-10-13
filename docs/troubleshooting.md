# Troubleshooting Guide

Common issues and solutions for ZK-Collector.

---

## Quick Diagnostics

### Health Check

```bash
# Check if collector is running
curl http://localhost:8080/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# Check collector logs
docker logs -f zk-collector
# or bare metal:
journalctl -u zk-collector -f
```

### Network Connectivity

```bash
# Test device reachability
ping 192.168.1.101

# Test ZKTeco port (4370)
nc -zv 192.168.1.101 4370
# Expected: Connection to 192.168.1.101 4370 port [tcp/*] succeeded!

# Test web dashboard
curl -v http://localhost:8080/health
```

---

## Common Issues

### 🔴 "Connection timeout" / "Device unreachable"

**Symptoms:**
- Device shows "offline" in dashboard
- Polling logs show connection errors
- `nc -zv` fails

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Device not on same LAN | Ensure collector and device share subnet |
| TCP/IP disabled on device | Menu → Comm → TCP/IP → Enable = YES |
| Wrong IP address | Verify device IP: Menu → Comm → TCP/IP → IP Address |
| Firewall blocking port 4370 | `sudo ufw allow out 4370/tcp` (collector) |
| VLAN isolation | Put collector and device on same VLAN |
| Cable/port issue | Try different cable/switch port |
| Device needs reboot | Power cycle the ZKTeco device |

**Debug steps:**
```bash
# 1. Ping test
ping -c 3 192.168.1.101

# 2. Port test
nc -zv 192.168.1.101 4370

# 3. Check device menu
# Menu → Comm → TCP/IP → ensure all enabled

# 4. Check collector logs
docker logs zk-collector | grep -i "error\|timeout"
```

---

### 🔴 "Authentication failed" / "Wrong password"

**Symptoms:**
- Connection succeeds but authentication fails
- Logs show "Auth failed" or "Invalid password"

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Default password is not 0 | Try: 0, 1, 2, 3... up to 999999 |
| Device has custom comm key | Check device: Menu → Comm → TCP/IP → Password |
| Password is 6 digits | Some models use 000000-999999 format |
| Key changed after firmware update | Reset to default (usually 0) |

**Debug steps:**
```bash
# Test with different passwords
for p in 0 1 2 3 4 5 6 7 8 9 1234 123456 000000; do
  python3 -c "
from zk import ZK
zk = ZK('192.168.1.101', port=4370, timeout=5, password=$p)
try:
    conn = zk.connect()
    if conn:
        print(f'SUCCESS with password: $p')
        zk.disconnect()
        break
except:
    pass
"
done
```

---

### 🔴 "No attendance records collected"

**Symptoms:**
- Device shows "online" but no records appear
- Dashboard shows 0 records

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| No users enrolled | Enroll fingerprints/cards on device |
| Device time is wrong | Sync device time (NTP or manual) |
| Poll interval too long | Reduce `poll_interval_seconds` in config |
| Records already read | Check `clear_after_read` setting |
| Device in wrong mode | Ensure not in "Test" or "Disabled" mode |

**Debug steps:**
```bash
# 1. Check device has users
# Menu → User Mgt → check enrolled users

# 2. Test manual download
# Use device USB backup to verify records exist

# 3. Force immediate poll
# Dashboard → Devices → "Sync Now"

# 4. Check buffer directly
sqlite3 /opt/attendance/data/buffer.db "SELECT COUNT(*) FROM attendance;"
```

---

### 🔴 "Garbled data" / "Malformed records"

**Symptoms:**
- Records show wrong timestamps or user IDs
- Encoding errors in logs

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Firmware too old | Update to V6.0+ (check [devices.md](devices.md)) |
| UDP packet loss | Switch to TCP in config (`protocol: "tcp"`) |
| Network interference | Check for duplex mismatch, replace cable |
| Device buffer overflow | Reduce poll interval, increase device capacity |

---

### 🔴 "Web dashboard not accessible"

**Symptoms:**
- Browser shows "Cannot connect" or times out
- Health endpoint works but UI doesn't load

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Wrong port | Default is 8080, check `PORT` env var |
| Firewall blocking 8080 | `sudo ufw allow 8080/tcp` |
| Docker port mapping | Verify `docker ps` shows `0.0.0.0:8080->8080/tcp` |
| Reverse proxy misconfig | Check nginx/Caddy config |
| SELinux/AppArmor | Check audit logs: `ausearch -m avc -ts recent` |

---

### 🔴 "Cloud sync failing"

**Symptoms:**
- Sync status shows "failed" or pending records accumulate
- Logs show HTTP errors

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Invalid API key | Verify `PLATFORM_API_KEY` in config/env |
| Wrong platform URL | Check `platform.url` (must include `/api`) |
| Network blocked | Ensure collector can reach internet |
| TLS/SSL issues | Verify certs, try `curl -v https://api.example.com/health` |
| Tenant ID mismatch | Verify `TENANT_ID` matches platform |
| Rate limited | Check sync interval (default 60s) |

**Debug steps:**
```bash
# Test platform connectivity
curl -v -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.example.com/health

# Check sync logs
docker logs zk-collector | grep -i "sync\|platform"

# Manual sync trigger
curl -b cookies.txt -X POST http://localhost:8080/devices/api/sync/trigger
```

---

### 🔴 "Forgot admin password"

**Solution:**
```bash
# Docker
docker exec -it zk-collector rm /app/data/webgui.db
docker restart zk-collector
# Then re-run setup at http://localhost:8080/auth/setup

# Bare metal
rm /opt/attendance/data/webgui.db
systemctl restart zk-collector
# Then re-run setup
```

---

### 🔴 "High memory/CPU usage"

**Symptoms:**
- Container/pocess uses excessive resources
- System becomes unresponsive

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Too many devices | Limit to 20 devices per collector instance |
| Poll interval too short | Increase `poll_interval_seconds` (min 60) |
| Large buffer | Reduce `buffer.max_records` |
| Memory leak | Update to latest version, restart periodically |

---

## Firewall & Network Configuration

### Required Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 8080 | TCP | Inbound | Web dashboard |
| 4370 | TCP/UDP | Outbound | ZKTeco device communication |
| 443 | TCP | Outbound | Cloud sync (HTTPS) |

### UFW (Ubuntu/Debian)

```bash
# Allow web dashboard (adjust source as needed)
sudo ufw allow from 192.168.1.0/24 to any port 8080

# Allow outbound to ZKTeco devices
sudo ufw allow out to 192.168.1.101 port 4370
sudo ufw allow out to 192.168.1.102 port 4370

# Allow HTTPS for cloud sync
sudo ufw allow out 443/tcp

# Enable
sudo ufw enable
```

### iptables (Raw)

```bash
# Inbound web dashboard
iptables -A INPUT -p tcp --dport 8080 -s 192.168.1.0/24 -j ACCEPT

# Outbound to devices
iptables -A OUTPUT -p tcp --dport 4370 -d 192.168.1.101 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 4370 -d 192.168.1.102 -j ACCEPT

# Outbound HTTPS
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
```

### Docker Network

```yaml
# docker-compose.yml - isolate from host network
services:
  zk-collector:
    network_mode: bridge  # default, isolates container
    # Use host network ONLY if device discovery needed:
    # network_mode: host
```

---

## Log Analysis

### Log Locations

| Deployment | Log Location |
|------------|--------------|
| Docker | `docker logs zk-collector` |
| systemd | `journalctl -u zk-collector` |
| Bare metal | `/var/log/attendance/collector.log` |

### Key Log Patterns

```bash
# Connection errors
docker logs zk-collector | grep -i "connect\|timeout\|refused"

# Sync errors
docker logs zk-collector | grep -i "sync\|platform\|http"

# Authentication
docker logs zk-collector | grep -i "auth\|password\|login"

# Device polling
docker logs zk-collector | grep -i "poll\|attendance\|record"
```

### Log Levels

```yaml
# In devices.yaml or env var LOG_LEVEL
logging:
  level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

---

## Getting Help

### Before Opening an Issue

1. **Collect diagnostics:**
   ```bash
   # System info
   uname -a
   python3 --version
   docker version  # if using Docker
   
   # Collector logs (last 100 lines)
   docker logs zk-collector --tail 100 > collector-logs.txt
   
   # Config (sanitized)
   cat configs/devices.yaml | sed 's/password: .*/password: ***/' > config.txt
   ```

2. **Check existing issues:** Search GitHub issues first

3. **Use the issue template:** Fill out all sections

### Useful Debug Commands

```bash
# Full system snapshot
{
  echo "=== System ==="; uname -a
  echo "=== Python ==="; python3 --version
  echo "=== Disk ==="; df -h /opt/attendance/data
  echo "=== Memory ==="; free -h
  echo "=== Network ==="; ip addr show
  echo "=== Devices ==="; cat configs/devices.yaml
  echo "=== Logs ==="; docker logs zk-collector --tail 50
} > debug-snapshot.txt
```

---

## Device-Specific Issues

See [Device Compatibility Matrix](devices.md) for model-specific troubleshooting.

| Model | Known Issue | Workaround |
|-------|-------------|------------|
| SpeedFace V5L | Face templates not readable | Use fingerprint/card only |
| U160 WiFi | Unstable WiFi | Use Ethernet instead |
| K40 | Occasional USB conflicts | Disable USB in device menu |

---

*Last updated: 2026-01-15*
*Version: 1.0.0*
