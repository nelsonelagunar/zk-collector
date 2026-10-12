"""
ZK Module - Cliente para dispositivos ZKTeco
"""

from .discovery import ZKDiscovery, discover_devices, DiscoveredDevice

__all__ = ['ZKDiscovery', 'discover_devices', 'DiscoveredDevice']
