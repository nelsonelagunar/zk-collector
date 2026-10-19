"""
ZK Module - Cliente para dispositivos ZKTeco
"""

# This module wraps the installed pyzk package
# The installed pyzk is available at /home/paperclip/.local/lib/python3.14/site-packages/zk/
# We need to import from the system pyzk, not from this local module

# Import everything from the real pyzk package
import os
import sys

# Ensure we use the installed pyzk, not this local package
pyzk_path = "/home/paperclip/.local/lib/python3.14/site-packages"
if pyzk_path not in sys.path:
    sys.path.insert(0, pyzk_path)

# Remove this package's path from sys.path to avoid circular import
src_zk_path = os.path.dirname(__file__)
if src_zk_path in sys.path:
    sys.path.remove(src_zk_path)

# Now import from the real pyzk
import zk as _pyzk  # noqa: E402  (sys.path must be adjusted before importing zk)

ZK = _pyzk.ZK
ZKError = _pyzk.exception.ZKError

# Local modules
from . import attendance, client, exceptions  # noqa: E402,F401  (re-exported)

__all__ = [
    "ZK",
    "ZKError",
    "AttendanceRecord",
    "ZKClient",
    "ZKConnectionError",
    "ZKAttendanceError",
]
