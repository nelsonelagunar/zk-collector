"""
ZKTeco Device Discovery - UDP Broadcast on port 4370
Implements LAN auto-discovery for ZKTeco devices
"""

import socket
import struct
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Module-level netifaces reference for patching in tests
netifaces = None
try:
    import netifaces as _netifaces
    netifaces = _netifaces
except ImportError:
    pass


@dataclass
class DiscoveredDevice:
    """Represents a discovered ZKTeco device"""
    ip: str
    port: int
    mac: str
    model: Optional[str] = None
    firmware: Optional[str] = None
    serial: Optional[str] = None
    device_name: Optional[str] = None
    protocol: str = "udp"

    def to_dict(self) -> Dict:
        return {
            'ip': self.ip,
            'port': self.port,
            'mac': self.mac,
            'model': self.model,
            'firmware': self.firmware,
            'serial': self.serial,
            'device_name': self.device_name,
            'protocol': self.protocol,
        }


class ZKDiscovery:
    """
    ZKTeco device discovery using UDP broadcast on port 4370

    ZKTeco devices respond to UDP broadcast packets with device information.
    The discovery protocol uses a simple request/response over UDP.
    """

    # ZKTeco discovery command (based on protocol reverse engineering)
    # This is a common discovery packet for ZKTeco devices
    DISCOVERY_CMD = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    def __init__(
        self,
        broadcast_address: str = '255.255.255.255',
        port: int = 4370,
        timeout: float = 3.0,
        retries: int = 2,
        rate_limit_delay: float = 0.1  # Delay between scans to respect rate limits
    ):
        self.broadcast_address = broadcast_address
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.rate_limit_delay = rate_limit_delay
        self._socket: Optional[socket.socket] = None

    def _create_socket(self) -> socket.socket:
        """Create UDP socket for broadcasting"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.timeout)
        return sock

    def _parse_discovery_response(self, data: bytes, addr: Tuple[str, int]) -> Optional[DiscoveredDevice]:
        """
        Parse ZKTeco discovery response

        Response format (typical):
        - Header: 8 bytes (command, sequence, etc.)
        - MAC address: 6 bytes
        - IP address: 4 bytes
        - Device info: variable
        """
        if len(data) < 10:  # Minimum expected response size (header + ip + mac = 14, but allow shorter)
            return None

        try:
            # ZKTeco devices typically respond with:
            # Offset 0-1: Command/Response code
            # Offset 2-3: Session/Sequence
            # Offset 4-7: Device IP (4 bytes)
            # Offset 8-13: MAC address (6 bytes)
            # Offset 14+: Additional info (model, firmware, etc.)

            # Extract MAC (6 bytes at offset 8 typically)
            # For short responses (< 14 bytes), use last 6 bytes
            if len(data) >= 14:
                mac_bytes = data[8:14]
            else:
                mac_bytes = data[-6:] if len(data) >= 6 else None
            
            if mac_bytes is None or len(mac_bytes) != 6:
                return None
            mac = ':'.join(f'{b:02x}' for b in mac_bytes).upper()

            # Extract IP (4 bytes at offset 4 typically)
            ip_bytes = data[4:8] if len(data) >= 8 else None
            if ip_bytes and len(ip_bytes) == 4 and ip_bytes != b'\x00\x00\x00\x00':
                ip = '.'.join(str(b) for b in ip_bytes)
            else:
                ip = addr[0]

            # Try to extract additional info from response
            model = None
            firmware = None
            serial = None
            device_name = None

            # Some devices include model/firmware in response
            # Expected format: header(4) + ip(4) + mac(6) = 14 bytes minimum, then text at offset 14+
            if len(data) > 14:
                # Try to decode ASCII strings from response
                try:
                    # Look for null-terminated strings in the response (starting at offset 14)
                    text_part = data[14:].decode('ascii', errors='ignore')
                    parts = [p for p in text_part.split('\x00') if p.strip()]
                    if parts:
                        model = parts[0] if len(parts) > 0 else None
                        firmware = parts[1] if len(parts) > 1 else None
                        serial = parts[2] if len(parts) > 2 else None
                        device_name = parts[3] if len(parts) > 3 else None
                except:
                    pass

            return DiscoveredDevice(
                ip=ip,
                port=self.port,
                mac=mac,
                model=model,
                firmware=firmware,
                serial=serial,
                device_name=device_name,
            )

        except Exception as e:
            logger.debug(f"Failed to parse discovery response from {addr}: {e}")
            return None

    def discover(self, network: Optional[str] = None) -> List[DiscoveredDevice]:
        """
        Discover ZKTeco devices on the network using UDP broadcast

        Args:
            network: Optional network CIDR (e.g., "192.168.1.0/24") to limit scan
                    If None, uses broadcast to all interfaces

        Returns:
            List of discovered devices
        """
        devices: List[DiscoveredDevice] = []
        seen_macs = set()

        # Determine broadcast addresses to use
        broadcast_addrs = self._get_broadcast_addresses(network)

        for broadcast_addr in broadcast_addrs:
            logger.info(f"Broadcasting discovery on {broadcast_addr}:{self.port}")

            for attempt in range(self.retries + 1):
                sock = self._create_socket()

                try:
                    # Send discovery broadcast
                    sock.sendto(self.DISCOVERY_CMD, (broadcast_addr, self.port))
                    logger.debug(f"Sent discovery broadcast (attempt {attempt + 1})")

                    # Listen for responses
                    start_time = time.time()
                    while time.time() - start_time < self.timeout:
                        try:
                            data, addr = sock.recvfrom(1024)
                            device = self._parse_discovery_response(data, addr)

                            if device and device.mac not in seen_macs:
                                seen_macs.add(device.mac)
                                devices.append(device)
                                logger.info(f"Discovered device: {device.ip} ({device.mac}) - {device.model or 'Unknown'}")

                        except socket.timeout:
                            break
                        except Exception as e:
                            logger.debug(f"Error receiving discovery response: {e}")
                            continue

                    # Small delay between retries to respect rate limits
                    if attempt < self.retries:
                        time.sleep(self.rate_limit_delay)

                except Exception as e:
                    logger.error(f"Discovery error on {broadcast_addr}: {e}")
                finally:
                    sock.close()

        logger.info(f"Discovery complete: found {len(devices)} device(s)")
        return devices

    def _get_broadcast_addresses(self, network: Optional[str] = None) -> List[str]:
        """Get list of broadcast addresses to use for discovery"""
        addrs = []

        if network:
            # Parse CIDR and calculate broadcast
            try:
                import ipaddress
                net = ipaddress.IPv4Network(network, strict=False)
                addrs.append(str(net.broadcast_address))
            except:
                pass
        else:
            # Get all interface broadcast addresses
            try:
                import netifaces
                for iface in netifaces.interfaces():
                    addrs_info = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs_info:
                        for addr_info in addrs_info[netifaces.AF_INET]:
                            if 'broadcast' in addr_info:
                                addrs.append(addr_info['broadcast'])
            except ImportError:
                # Fallback to common broadcast addresses
                addrs = ['255.255.255.255', '192.168.1.255', '192.168.0.255', '10.255.255.255']

        # Ensure we have at least the global broadcast
        if not addrs:
            addrs = ['255.255.255.255']

        return list(set(addrs))  # Deduplicate

    def discover_with_details(self, network: Optional[str] = None) -> List[DiscoveredDevice]:
        """
        Discover devices and fetch detailed info via TCP connection

        This does a two-phase discovery:
        1. UDP broadcast to find devices
        2. TCP connection to each device to get detailed info

        Args:
            network: Optional network CIDR

        Returns:
            List of devices with detailed information
        """
        # Phase 1: UDP discovery
        devices = self.discover(network)

        # Phase 2: Get detailed info via TCP (parallel, with rate limiting)
        detailed_devices = []

        def fetch_details(device: DiscoveredDevice) -> DiscoveredDevice:
            try:
                # Try to connect via TCP to get detailed info
                from zk import ZK
                zk = ZK(device.ip, port=device.port, timeout=5, password=0, force_udp=False)
                conn = zk.connect()
                if conn:
                    device.model = conn.get_device_name() or device.model
                    device.firmware = conn.get_firmware_version() or device.firmware
                    device.serial = conn.get_serialnumber() or device.serial
                    device.mac = conn.get_mac() or device.mac
                    conn.disconnect()
            except Exception as e:
                logger.debug(f"Could not fetch details for {device.ip}: {e}")
            return device

        # Use ThreadPoolExecutor with limited workers to respect rate limits
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_device = {executor.submit(fetch_details, d): d for d in devices}
            for future in as_completed(future_to_device):
                detailed_devices.append(future.result())
                time.sleep(self.rate_limit_delay)  # Rate limiting

        return detailed_devices


def discover_devices(
    network: Optional[str] = None,
    timeout: float = 3.0,
    retries: int = 2,
    fetch_details: bool = True
) -> List[Dict]:
    """
    Convenience function for device discovery

    Args:
        network: Optional network CIDR (e.g., "192.168.1.0/24")
        timeout: Discovery timeout in seconds
        retries: Number of broadcast retries
        fetch_details: Whether to fetch detailed info via TCP

    Returns:
        List of device dictionaries
    """
    discovery = ZKDiscovery(timeout=timeout, retries=retries)

    if fetch_details:
        devices = discovery.discover_with_details(network)
    else:
        devices = discovery.discover(network)

    return [d.to_dict() for d in devices]