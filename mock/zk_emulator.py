#!/usr/bin/env python3
"""
ZKTeco TCP Emulator (asyncio)
Implements subset of pyzk protocol for testing collector without physical device
Listens on port 4370
"""

import asyncio
import json
import os
import struct
from datetime import datetime
from pathlib import Path

# pyzk constants
CMD_CONNECT = 1000
CMD_EXIT = 1001
CMD_ENABLEDEVICE = 1002
CMD_DISABLEDEVICE = 1003
CMD_GET_TIME = 201
CMD_SET_TIME = 202
CMD_GET_FREE_SIZES = 50
CMD_ATTLOG_RRQ = 13
CMD_USERTEMP_RRQ = 9
CMD_GET_VERSION = 1100
CMD_OPTIONS_RRQ = 11
CMD_PREPARE_DATA = 1500
CMD_DATA = 1501
CMD_FREE_DATA = 1502
CMD_AUTH = 1102
CMD_REFRESHDATA = 20  # Refresh data command
CMD_ACK_OK = 2000
CMD_ACK_UNAUTH = 2005
CMD_ACK_ERROR = 2001
MACHINE_PREPARE_DATA_1 = 20560
MACHINE_PREPARE_DATA_2 = 32130
USHRT_MAX = 65535
USER_DEFAULT = 0
FCT_USER = 5

# Response sizes
RESPONSE_SIZE = 1024

# Device info
DEVICE_FIRMWARE = "6.60"
DEVICE_SERIAL = "EMU123456"
DEVICE_PLATFORM = "ZKEmulator"
DEVICE_NAME = "ZKTeco Emulator"
DEVICE_MAC = "00:11:22:33:44:55"


def calculate_checksum(data: bytes) -> int:
    """Calculate checksum like pyzk does"""
    length = len(data)
    checksum = 0
    while length > 1:
        checksum += struct.unpack('H', struct.pack('BB', data[0], data[1]))[0]
        data = data[2:]
        if checksum > USHRT_MAX:
            checksum -= USHRT_MAX
        length -= 2
    if length:
        checksum = checksum + data[-1]
    while checksum > USHRT_MAX:
        checksum -= USHRT_MAX
    checksum = ~checksum
    while checksum < 0:
        checksum += USHRT_MAX
    return checksum


def encode_time(dt: datetime) -> int:
    """Encode datetime to ZK timestamp format"""
    d = (
        ((dt.year % 100) * 12 * 31 + ((dt.month - 1) * 31) + dt.day - 1)
        * (24 * 60 * 60)
        + (dt.hour * 60 + dt.minute) * 60
        + dt.second
    )
    return d


def make_commkey(key: int, session_id: int, ticks: int = 50) -> bytes:
    """Generate authentication key like pyzk"""
    key = int(key)
    session_id = int(session_id)
    k = 0
    for i in range(32):
        k = k << 1 | 1 if key & (1 << i) else k << 1
    k += session_id

    k = struct.pack('I', k)
    k = struct.unpack('BBBB', k)
    k = struct.pack(
        'BBBB',
        k[0] ^ ord('Z'),
        k[1] ^ ord('K'),
        k[2] ^ ord('S'),
        k[3] ^ ord('O')
    )
    k = struct.unpack('HH', k)
    k = struct.pack('HH', k[1], k[0])

    b = 0xff & ticks
    k = struct.unpack('BBBB', k)

    return struct.pack('BBBB', k[0] ^ b, k[1] ^ b, k[2] ^ b, k[3] ^ b)


class ZKEmulator:
    """Asyncio TCP server emulating ZKTeco device"""

    def __init__(self, host: str = "0.0.0.0", port: int = 4370):
        self.host = host
        self.port = port
        self.session_id = 0
        self.reply_id = USHRT_MAX - 1
        self.connected = False
        self.enabled = True
        self.password = 0
        self.tcp_mode = True

        # Load attendance seed
        self.attendance_records = self._load_attendance_seed()
        self.users = self._get_synthetic_users()

    def _load_attendance_seed(self) -> list[dict]:
        """Load attendance records from env var or file"""
        # Try env var first
        env_records = os.environ.get("MOCK_ATTENDANCE_RECORDS")
        if env_records:
            try:
                return json.loads(env_records)
            except json.JSONDecodeError:
                pass

        # Try file
        seed_file = Path(__file__).parent / "attendance_seed.json"
        if seed_file.exists():
            try:
                with open(seed_file) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        # Default fallback
        return [
            {"user_id": "1", "timestamp": "2026-03-03 08:00:00", "status": 0},
            {"user_id": "1", "timestamp": "2026-03-03 12:00:00", "status": 1},
            {"user_id": "1", "timestamp": "2026-03-03 13:00:00", "status": 0},
            {"user_id": "1", "timestamp": "2026-03-03 17:00:00", "status": 1},
            {"user_id": "1", "timestamp": "2026-03-04 08:05:00", "status": 0},
            {"user_id": "1", "timestamp": "2026-03-04 12:00:00", "status": 1},
            {"user_id": "2", "timestamp": "2026-03-03 08:15:00", "status": 0},
            {"user_id": "2", "timestamp": "2026-03-03 12:00:00", "status": 1},
            {"user_id": "2", "timestamp": "2026-03-03 13:00:00", "status": 0},
            {"user_id": "2", "timestamp": "2026-03-03 17:00:00", "status": 1},
            {"user_id": "3", "timestamp": "2026-03-03 08:30:00", "status": 0},
            {"user_id": "3", "timestamp": "2026-03-03 17:30:00", "status": 1},
        ]

    def _get_synthetic_users(self) -> list[dict]:
        """Return synthetic user data"""
        return [
            {"uid": 1, "user_id": "1", "name": "Test User 1", "privilege": 0, "password": ""},
            {"uid": 2, "user_id": "2", "name": "Test User 2", "privilege": 0, "password": ""},
            {"uid": 3, "user_id": "3", "name": "Test User 3", "privilege": 0, "password": ""},
        ]

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connection"""
        addr = writer.get_extra_info("peername")
        print(f"Client connected: {addr}")

        try:
            while True:
                # Read TCP header (8 bytes: H H I)
                header = await reader.read(8)
                if not header or len(header) < 8:
                    break

                top = struct.unpack("<HHI", header)
                if top[0] != MACHINE_PREPARE_DATA_1 or top[1] != MACHINE_PREPARE_DATA_2:
                    # Not a TCP-wrapped packet, try raw
                    inner = header + await reader.read(1024)
                else:
                    length = top[2]
                    inner = await reader.read(length)

                if not inner:
                    break

                # Parse command
                cmd_header = struct.unpack("<4H", inner[:8])
                command = cmd_header[0]
                session_id = cmd_header[2]

                if command == CMD_CONNECT:
                    self.connected = True
                    self.session_id = 1
                    response = self._make_response(CMD_ACK_OK, b"", session_id)
                    writer.write(response)
                    await writer.drain()
                    print(f"Client {addr}: CONNECT OK")

                elif command == CMD_EXIT:
                    print(f"Client {addr}: EXIT")
                    response = self._make_response(CMD_ACK_OK, b"", session_id)
                    writer.write(response)
                    await writer.drain()
                    break

                elif command == CMD_GET_TIME:
                    now = datetime.now()
                    timestamp = encode_time(now)
                    payload = struct.pack("<I", timestamp)
                    response = self._make_response(CMD_ACK_OK, payload, session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_GET_FREE_SIZES:
                    # Exactly 20 integers for "<20i"
                    payload = struct.pack(
                        "<20i",
                        0,     # 0
                        0,     # 1
                        0,     # 2
                        0,     # 3
                        3,     # 4: users
                        0,     # 5
                        100,   # 6: fingers
                        0,     # 7
                        len(self.attendance_records),  # 8: records
                        0,     # 9
                        0,     # 10
                        0,     # 11
                        0,     # 12: cards
                        0,     # 13
                        0,     # 14
                        100,   # 15: fingers_cap
                        10,    # 16: users_cap
                        10000, # 17: rec_cap
                        97,    # 18: fingers_av
                        7,     # 19: users_av
                    )
                    response = self._make_response(CMD_ACK_OK, payload, session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_USERTEMP_RRQ:
                    # Build user data: 4-byte total size + N * 28-byte records
                    user_data = b""
                    for user in self.users:
                        user_record = struct.pack(
                            "<HB5s8sIxBhI",
                            user["uid"],           # H: uid
                            user["privilege"],      # B: privilege
                            user["password"].encode()[:5].ljust(5, b"\x00"),  # 5s: password
                            user["name"].encode()[:8].ljust(8, b"\x00"),      # 8s: name
                            0,                      # I: card
                            # x: padding (no value needed)
                            0,                      # B: group_id
                            0,                      # h: timezone
                            int(user["user_id"]),   # I: user_id
                        )
                        user_data += user_record

                    total_size = len(user_data)
                    payload = struct.pack("<I", total_size) + user_data
                    response = self._make_response(CMD_ACK_OK, payload, session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_ATTLOG_RRQ:
                    # Always return attendance records regardless of enabled state
                    # (disable/enable in real device prevents NEW records, not reading existing)

                    # Build attendance data: 4-byte total size + N * 8-byte records
                    att_data = b""
                    for record in self.attendance_records:
                        dt = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
                        timestamp = encode_time(dt)
                        att_record = struct.pack(
                            "<HB4sB",
                            int(record["user_id"]),    # H: user_id
                            record["status"],          # B: status (0=check-in, 1=check-out)
                            struct.pack("<I", timestamp),  # 4s: timestamp
                            0,                          # B: punch
                        )
                        att_data += att_record

                    total_size = len(att_data)
                    payload = struct.pack("<I", total_size) + att_data
                    response = self._make_response(CMD_ACK_OK, payload, session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_DISABLEDEVICE:
                    self.enabled = False
                    response = self._make_response(CMD_ACK_OK, b"", session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_ENABLEDEVICE:
                    self.enabled = True
                    response = self._make_response(CMD_ACK_OK, b"", session_id)
                    writer.write(response)
                    await writer.drain()

                elif command == CMD_GET_VERSION:
                    payload = DEVICE_FIRMWARE.encode() + b"\x00"
                    response = self._make_response(CMD_ACK_OK, payload, session_id)
                    writer.write(response)
                    await writer.drain()

                else:
                    print(f"Unknown command: {command}")
                    response = self._make_response(CMD_ACK_ERROR, b"", session_id)
                    writer.write(response)
                    await writer.drain()

        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"Client disconnected: {addr}")

    def _make_response(self, command: int, command_string: bytes, session_id: int) -> bytes:
        """Build response packet with TCP header"""
        buf = struct.pack("<4H", command, 0, session_id, self.reply_id) + command_string
        buf_bytes = bytearray(buf)
        checksum = calculate_checksum(bytes(buf_bytes))
        next_reply = self.reply_id + 1
        new_reply = next_reply if next_reply < USHRT_MAX else next_reply - USHRT_MAX
        inner = struct.pack("<4H", command, checksum, session_id, new_reply) + command_string
        tcp_header = struct.pack("<HHI", MACHINE_PREPARE_DATA_1, MACHINE_PREPARE_DATA_2, len(inner))
        self.reply_id = new_reply
        return tcp_header + inner


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Standalone handler function for tests"""
    emulator = ZKEmulator()
    await emulator.handle_client(reader, writer)


async def main():
    """Run emulator as standalone server"""
    emulator = ZKEmulator()
    server = await asyncio.start_server(
        emulator.handle_client, emulator.host, emulator.port
    )
    print(f"ZK Emulator listening on {emulator.host}:{emulator.port}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
