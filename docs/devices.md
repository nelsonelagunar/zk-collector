## Device Compatibility

ZK-Collector uses the [pyzk](https://github.com/fananimi/pyzk) library to communicate with ZKTeco devices via their proprietary TCP/UDP protocol.

### Tested Models

| Model | Status | Notes |
|-------|--------|-------|
| ZKTeco K40 | ✅ Full | Fingerprint + card reader |
| ZKTeco U160 | ✅ Full | Network attendance terminal |
| ZKTeco X628 | ✅ Full | Fingerprint time & attendance |
| ZKTeco iClock 3000 | ✅ Full | Biometric time clock |
| ZKTeco SpeedFace V5L | ⚠️ Partial | Attendance works, face recognition data not supported |

### How to Test Your Device

1. Find your device's IP address (check your router's DHCP lease table)
2. Ensure the collector machine can ping the device
3. Add the device in the ZK-Collector web dashboard
4. Click "Test Connection"
5. If it works, open an issue using the [Device Compatibility template](https://github.com/nelsonelagunar/zk-collector/issues/new?template=device_compatibility.md)

### Common Issues

**"Connection timeout"**
- Device and collector must be on the same subnet
- Some ZKTeco devices have a "TCP/IP" setting that must be enabled
- Default port is 4370; some models use different ports

**"Authentication failed"**
- Default device communication password is usually `0`
- Check the device's comm key in its settings menu

**"No attendance records"**
- Ensure employees have enrolled fingerprints/cards on the device
- Try pulling records manually first (device menu → USB download)
