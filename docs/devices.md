# Device Compatibility Matrix

ZK-Collector uses the [pyzk](https://github.com/fananimi/pyzk) library to communicate with ZKTeco devices via their proprietary TCP/UDP protocol on port 4370.

## Compatibility Badges

| Model | Status | Badges |
|-------|--------|--------|
| ZKTeco K40 | ✅ Full | ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) |
| ZKTeco U160 | ✅ Full | ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) ![WiFi](https://img.shields.io/badge/WiFi-⚠️-yellow.svg) |
| ZKTeco X628 | ✅ Full | ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) |
| ZKTeco iClock 3000 | ✅ Full | ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) ![USB](https://img.shields.io/badge/USB-✅-green.svg) |
| ZKTeco SpeedFace V5L | ⚠️ Partial | ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Face](https://img.shields.io/badge/Face-❌-red.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) ![WiFi](https://img.shields.io/badge/WiFi-✅-blue.svg) |
| ZKTeco SpeedFace V5L [P] | ⚠️ Partial | ![Palm](https://img.shields.io/badge/Palm-❌-red.svg) ![Face](https://img.shields.io/badge/Face-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) |
| ZKTeco FaceKare V5L | ⚠️ Partial | ![Face](https://img.shields.io/badge/Face-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) |
| ZKTeco MB10-VL | ⚠️ Partial | ![Face](https://img.shields.io/badge/Face-✅-blue.svg) ![Fingerprint](https://img.shields.io/badge/Fingerprint-✅-blue.svg) ![Card](https://img.shields.io/badge/Card-✅-blue.svg) ![Password](https://img.shields.io/badge/Password-✅-blue.svg) ![LAN](https://img.shields.io/badge/LAN-✅-blue.svg) |
| ZKTeco G4 | ❌ Not Tested | — |
| ZKTeco F18 | ❌ Not Tested | — |
| ZKTeco K14 | ❌ Not Tested | — |

*Badges indicate tested functionality. Blank means not verified.*

## Detailed Compatibility Table

| Model | Fingerprint | Face | Palm | Card | Password | LAN | WiFi | USB | Notes |
|-------|-------------|------|------|------|----------|-----|------|-----|-------|
| ZKTeco K40 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | Basic time attendance terminal |
| ZKTeco U160 | ✅ | ❌ | � ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Network terminal with optional WiFi |
| ZKTeco X628 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | Wall-mounted fingerprint reader |
| ZKTeco iClock 3000 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | Biometric time clock with USB backup |
| ZKTeco SpeedFace V5L | ✅ | ⚠️ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | Face recognition data not extracted |
| ZKTeco SpeedFace V5L [P] | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | Palm verification works, face not tested |
| ZKTeco FaceKare V5L | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | Face recognition primary |
| ZKTeco MB10-VL | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | Multi-biometric terminal |
| ZKTeco G4 | ? | ? | ? | ? | ? | ? | ? | ? | Community reports welcome |
| ZKTeco F18 | ? | ? | ? | ? | ? | ? | ? | ? | Community reports welcome |
| ZKTeco K14 | ? | ? | ? | ? | ? | ? | ? | ? | Community reports welcome |

## Firmware Requirements

Most ZKTeco devices require firmware version **V6.0 or later** for stable TCP/IP communication.

To check firmware version:
1. Go to device menu → About → Version
2. Or check via ZK-Collector web dashboard after adding device

**Minimum tested firmware:**
- K40: V6.2.1
- U160: V6.3.1
- X628: V6.0.2
- iClock 3000: V6.1.0

## Device Configuration

### Required Settings on Device

For proper communication with ZK-Collector:

1. **TCP/IP Enabled** (Must be ON)
   - Menu → Comm → TCP/IP → TCP/IP Enabled = YES

2. **IP Address Configuration**
   - Menu → Comm → TCP/IP → IP Address = [Static IP in your LAN]
   - Menu → Comm → TCP/IP → Subnet Mask = [Usually 255.255.255.0]
   - Menu → Comm → TCP/IP → Gateway = [Your router IP]

3. **Port Number**
   - Menu → Comm → TCP/IP → Port Number = **4370** (default)
   - Some models allow changing; ensure it matches ZK-Collector config

4. **Connection Password / Comm Key**
   - Menu → Comm → TCP/IP → Password = [Usually 0 for default]
   - Must match `password` field in ZK-Collector device config

5. **Protocol**
   - Menu → Comm → TCP/IP → Protocol = **TCP** (UDP also works if configured)
   - Matches `protocol` field in ZK-Collector (tcp/udp)

### Network Requirements

| Requirement | Specification |
|-------------|---------------|
| **Physical Layer** | Ethernet 10/100 Mbps (RJ45) |
| **IP Version** | IPv4 only (IPv6 not supported) |
| **Port Access** | TCP/UDP 4370 open between collector and device |
| **Latency** | <100ms recommended for responsive UI |
| **Bandwidth** | Minimal (<1 kbps per device) |
| **Firewall** | Allow outbound 4370 from collector to device IP |

## Testing Your Device

### Quick Verification Steps

1. **Ping Test** (from collector machine):
   ```bash
   ping 192.168.1.101  # Replace with device IP
   ```

2. **Port Test** (from collector machine):
   ```bash
   # TCP test
   nc -zv 192.168.1.101 4370
   # UDP test (if using UDP)
   nc -zu 192.168.1.101 4370
   ```

3. **ZK-Collector Test Connection**
   - Add device in web dashboard
   - Click "Test Connection" button
   - Check logs for detailed output

### Common Issues & Solutions

#### 🔴 "Connection timeout"
- **Cause**: Device unreachable on port 4370
- **Solutions**:
  - Verify device and collector on same subnet
  - Check device TCP/IP setting is ENABLED
  - Confirm no firewall blocking port 4370
  - Try different Ethernet cable/port
  - Power cycle the device

#### 🔴 "Authentication failed"
- **Cause**: Wrong comm key/password
- **Solutions**:
  - Default password is usually `0`
  - Check device menu → Comm → TCP/IP → Password
  - Some models use 6-digit passwords (000000-999999)
  - Try incrementing from 0: 0, 1, 2, 3...

#### 🔴 "No attendance records"
- **Cause**: Device not capturing data
- **Solutions**:
  - Verify users have enrolled fingerprints/cards
  - Check device time is correct
  - Test manual download via device USB menu
  - Ensure device is not in "disabled" or "test" mode

#### 🔴 "Device returns garbled data"
- **Cause**: Firmware mismatch or partial packets
- **Solutions**:
  - Update device firmware to latest version
  - Reduce polling interval (increases reliability)
  - Check for network interference
  - Use TCP instead of UDP if experiencing packet loss

## Adding New Device Models

If your ZKTeco model isn't listed:

1. **Basic Connect Test**
   ```bash
   python3 -c "
   from zk import ZK
   zk = ZK('192.168.1.100', port=4370, timeout=5, password=0)
   try:
       conn = zk.connect()
       if conn:
           print('Firmware:', zk.get_firmware_version())
           print('Serial:', zk.get_serialnumber())
           print('Platform:', zk.get_platform())
           zk.disable_device()
           attendance = zk.get_attendance()
           print(f'Retrieved {len(attendance)} records')
           zk.enable_device()
           zk.disconnect()
   except Exception as e:
       print('Error:', e)
   "
   ```

2. **Submit Compatibility Report**
   - Use the [Device Compatibility template](https://github.com/nelsonelagunar/zk-collector/issues/new?template=device_compatibility.md)
   - Include:
     - Exact model name (from device label)
     - Firmware version
     - Which features work/fail
     - Any special configuration needed
     - Test script output (if possible)

## Supported Features by Model Family

### K Series (K40, K14, K20, etc.)
- ✅ Fingerprint recognition
- ✅ Card reading (EM/HID/Mifare)
- ✅ Password input
- ❌ Face recognition
- ❌ Palm recognition
- 📝 Basic time & attendance

### U Series (U160, U180, U200, etc.)
- ✅ All K Series features
- ✅ Ethernet standard
- ✅ Optional WiFi module
- ✅ PoE (Power over Ethernet) on some models
- 📝 Network-attended terminals

### X Series (X628, X628-C, X790, etc.)
- ✅ Fingerprint
- ✅ Card
- ✅ Password
- ✅ LCD touchscreen (some models)
- 📝 Wall/desk mounted readers

### iClock Series
- ✅ Fingerprint
- ✅ Card
- ✅ Password
- ✅ USB host for flash drive backup
- 📝 Biometric time clocks

### Face/SpeedFace Series
- ✅ Face recognition (templates not extracted)
- ✅ Fingerprint
- ✅ Card
- ✅ Password
- ✅ LCD touchscreen
- ⚠️ Face data not accessible via pyzk library
- 📝 Multi-biometric terminals

## Firmware Update Recommendation

For best compatibility, update devices to latest firmware:

1. **Download** from ZKTeco official site (requires partner account)
2. **Update via**:
   - USB flash drive (most models)
   - TCP/IP using ZKTool software
   - Web interface (newer models)
3. **Verify** after update:
   - TCP/IP still enabled
   - Port 4370 open
   - Comm key unchanged (usually reset to 0)

## Mock Emulator (no hardware required)

For local development, CI or demos you can run a pure-Python ZKTeco TCP
emulator (`mock/zk_emulator.py`) instead of a physical device. It speaks the
ZK protocol (including the ZK6 buffered read used by `pyzk.get_attendance()`)
and serves synthetic records from `mock/attendance_seed.json`.

```bash
# Terminal 1 — start the emulator (listens on 0.0.0.0:4370)
python3 mock/zk_emulator.py

# Terminal 2 — point the collector at it
# configs/collector.yaml
devices:
  - ip: "127.0.0.1"
    port: 4370
    name: "Emulador ZK (mock)"
    enabled: true
    ommit_ping: true   # emulator implements TCP only, no ICMP ping
```

> **Note:** `ommit_ping: true` is required because the emulator does not
> answer `pyzk`'s reachability ping. Real devices normally keep the default
> (`false`).

The emulator is also exercised by the automated tests:

```bash
pytest tests/unit/test_zk_emulator.py tests/integration/test_emulator_integration.py -v
```

## Community Contributions

Device compatibility grows thanks to community reports. To contribute:

1. Test your device with ZK-Collector
2. Report results using [issue template](https://github.com/nelsonelagunar/zk-collector/issues/new?template=device_compatibility.md)
3. Include:
   - Model name (exact as printed)
   - Firmware version
   - Working/non-working features
   - Special notes or quirks
4. We'll add it to this matrix with appropriate badges

---

*Last updated: $(date +%Y-%m-%d)*
*Total models tested: 5*
*Community reports: 0 (be the first!)*
