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
    l = len(data)
    checksum = 0
    while l > 1:
        checksum += struct.unpack('H', struct.pack('BB', data[0], data[1]))[0]
        data = data[2:]
        if checksum > USHRT_MAX:
            checksum -= USHRT_MAX
        l -= 2
    if l:
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
        if key & (1 << i):
            k = (k << 1 | 1)
        else:
            k = k << 1
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

    B = 0xff & ticks
    k = struct.unpack('BBBB', k)

    return struct.pack('BBBB', k[0] ^ B, k[1] ^ B, k[2] ^ B, k[3] ^ B)


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
            {
                "user_id": "1",
                "timestamp": "2026-10-13T08:00:00",
                "status": 0,
                "punch_type": "check_in"
            }
        ]

    def _get_synthetic_users(self) -> list[dict]:
        """Return synthetic user list"""
        return [
            {"user_id": "1", "name": "Test User 1", "privilege": 0, "password": "", "uid": 1},
            {"user_id": "2", "name": "Test User 2", "privilege": 0, "password": "", "uid": 2},
            {"user_id": "3", "name": "Test User 3", "privilege": 0, "password": "", "uid": 3},
        ]

    def _create_header(self, command: int, command_string: bytes, session_id: int, reply_id: int) -> bytes:
        """Create command header"""
        buf = struct.pack('<4H', command, 0, session_id, reply_id) + command_string
        buf = struct.unpack('8B' + '%sB' % len(command_string), buf)
        checksum = calculate_checksum(bytes(buf))
        reply_id += 1
        if reply_id >= USHRT_MAX:
            reply_id -= USHRT_MAX
        buf = struct.pack('<4H', command, checksum, session_id, reply_id)
        return buf + command_string

    def _create_tcp_top(self, packet: bytes) -> bytes:
        """Add TCP header"""
        length = len(packet)
        top = struct.pack('<HHI', MACHINE_PREPARE_DATA_1, MACHINE_PREPARE_DATA_2, length)
        return top + packet

    def _create_response(self, command: int, status: bool, command_string: bytes = b'', session_id: int = 0, reply_id: int = USHRT_MAX - 1) -> bytes:
        """Create response packet"""
        if status:
            code = CMD_ACK_OK
        else:
            code = CMD_ACK_ERROR

        # For some commands, we return specific codes
        if command == CMD_CONNECT and not self.connected and status:
            code = CMD_ACK_OK
        elif command == CMD_CONNECT and not status:
            code = CMD_ACK_UNAUTH

        buf = struct.pack('<4H', command, 0, session_id, reply_id) + command_string
        buf = struct.unpack('8B' + '%sB' % len(command_string), buf)
        checksum = calculate_checksum(bytes(buf))
        reply_id += 1
        if reply_id >= USHRT_MAX:
            reply_id -= USHRT_MAX
        buf = struct.pack('<4H', command, checksum, session_id, reply_id)
        return buf + command_string

    def _get_time_response(self) -> bytes:
        """Generate get_time response"""
        now = datetime.now()
        encoded = encode_time(now)
        return struct.pack('I', encoded)

    def _get_free_sizes_response(self) -> bytes:
        """Generate get_free_sizes response - exactly 20 integers as per pyzk format"""
        users = len(self.users)
        fingers = 0
        records = len(self.attendance_records)
        dummy = 0
        cards = 0
        fingers_cap = 0
        users_cap = 1000
        rec_cap = 10000
        fingers_av = 0
        users_av = users_cap - users
        rec_av = rec_cap - records
        faces = 0
        faces_cap = 0

        # Match pyzk indices from read_sizes():
        # fields[4]=users, fields[6]=fingers, fields[8]=records, fields[9]=dummy
        # fields[12]=cards, fields[14]=fingers_cap, fields[15]=users_cap, fields[16]=rec_cap
        # fields[17]=fingers_av, fields[18]=users_av, fields[19]=rec_av
        fields = [
            0, 0, 0, 0,      # 0-3: unused
            users,            # 4: users
            0,                # 5: unused
            fingers,          # 6: fingers
            0,                # 7: unused
            records,          # 8: records
            dummy,            # 9: dummy
            0,                # 10: unused
            0,                # 11: unused
            cards,            # 12: cards
            0,                # 13: unused
            fingers_cap,      # 14: fingers_cap
            users_cap,        # 15: users_cap
            rec_cap,          # 16: rec_cap
            fingers_av,       # 17: fingers_av
            users_av,         # 18: users_av
            rec_av,           # 19: rec_av
        ]

        return struct.pack('<20i', *fields)

    def _get_users_response(self) -> bytes:
        """Generate user data response"""
        total_size = len(self.users) * 28  # Using 28-byte format (ZK6)
        header = struct.pack('I', total_size)

        data = header
        for user in self.users:
            uid = user["uid"]
            privilege = user["privilege"]
            password = user["password"].encode('utf-8', errors='ignore')
            name = user["name"].encode('utf-8', errors='ignore')
            card = 0
            group_id = 0
            timezone = 0
            user_id = int(user["user_id"])

            # Pack: uid (H), privilege (B), password (5s), name (8s), card (I), group_id (x B), timezone (h), user_id (I)
            # Note: the format is '<HB5s8sIxBhI' = 2+1+5+8+4+1+1+2+4 = 28
            user_data = struct.pack(
                '<HB5s8sIxBhI',
                uid,
                privilege,
                password.ljust(5, b'\x00')[:5],
                name.ljust(8, b'\x00')[:8],
                card,
                group_id,
                timezone,
                user_id
            )
            data += user_data

        return data

    def _get_attendance_response(self) -> bytes:
        """Generate attendance data response"""
        # Format: 8-byte records (ZK6 format)
        # uid (H), status (B), timestamp (4s), punch (B)
        total_size = len(self.attendance_records) * 8
        header = struct.pack('I', total_size)

        data = header
        for record in self.attendance_records:
            user_id = int(record["user_id"])
            status = record["status"]
            # Parse timestamp
            ts = datetime.fromisoformat(record["timestamp"].replace('Z', '+00:00'))
            encoded_time = encode_time(ts)
            timestamp_bytes = struct.pack('<I', encoded_time)
            punch = 0  # Not used in 8-byte format

            att_data = struct.pack('<HB4sB', user_id, status, timestamp_bytes, punch)
            data += att_data

        return data

    def _get_firmware_version(self) -> bytes:
        """Generate firmware version response"""
        return DEVICE_FIRMWARE.encode('utf-8') + b'\x00'

    def _get_options_response(self, option: str) -> bytes:
        """Generate options response"""
        options_map = {
            "SerialNumber": DEVICE_SERIAL,
            "Platform": DEVICE_PLATFORM,
            "DeviceName": DEVICE_NAME,
            "MAC": DEVICE_MAC,
        }
        value = options_map.get(option, "")
        return value.encode('utf-8')

    def _handle_command(self, command: int, command_string: bytes) -> tuple[int, bytes]:
        """Handle incoming command, return (response_code, response_data)"""
        if command == CMD_CONNECT:
            if self.password != 0:
                return CMD_ACK_UNAUTH, b''
            self.connected = True
            return CMD_ACK_OK, b''

        elif command == CMD_AUTH:
            # Verify commkey
            expected = make_commkey(self.password, self.session_id)
            if command_string == expected:
                self.connected = True
                return CMD_ACK_OK, b''
            return CMD_ACK_UNAUTH, b''

        elif command == CMD_EXIT:
            self.connected = False
            return CMD_ACK_OK, b''

        elif command == CMD_ENABLEDEVICE:
            self.enabled = True
            return CMD_ACK_OK, b''

        elif command == CMD_DISABLEDEVICE:
            self.enabled = False
            return CMD_ACK_OK, b''

        elif command == CMD_GET_TIME:
            return CMD_ACK_OK, self._get_time_response()

        elif command == CMD_SET_TIME:
            return CMD_ACK_OK, b''

        elif command == CMD_GET_FREE_SIZES:
            return CMD_ACK_OK, self._get_free_sizes_response()

        elif command == CMD_GET_VERSION:
            return CMD_ACK_OK, self._get_firmware_version()

        elif command == CMD_USERTEMP_RRQ:
            # Get users with FCT_USER (5)
            return CMD_ACK_OK, self._get_users_response()

        elif command == CMD_ATTLOG_RRQ:
            return CMD_ACK_OK, self._get_attendance_response()

        elif command == CMD_OPTIONS_RRQ:
            option = command_string.decode('utf-8', errors='ignore').strip('\x00')
            if option.startswith('~'):
                option = option[1:]
            return CMD_ACK_OK, self._get_options_response(option)

        elif command == CMD_PREPARE_DATA:
            # For buffered reads
            size = struct.unpack('I', command_string)[0]
            return CMD_ACK_OK, struct.pack('I', size)

        elif command == CMD_FREE_DATA:
            return CMD_ACK_OK, b''

        elif command == CMD_DATA:
            # Data chunk request
            return CMD_ACK_OK, b''

        elif command == CMD_REFRESHDATA:
            return CMD_ACK_OK, b''

        else:
            print(f"Unknown command: {command} (0x{command:04X})")
            return CMD_ACK_ERROR, b''

    def _process_packet(self, data: bytes) -> bytes | None:
        """Process incoming packet and generate response"""
        if len(data) < 8:
            return None

        # Parse TCP header if present
        offset = 0
        if len(data) >= 8:
            tcp_header = struct.unpack('<HHI', data[:8])
            if tcp_header[0] == MACHINE_PREPARE_DATA_1 and tcp_header[1] == MACHINE_PREPARE_DATA_2:
                # TCP mode
                expected_len = tcp_header[2]
                if len(data) < 8 + expected_len:
                    return None  # Need more data
                offset = 8
                data = data[8:8+expected_len]

        # Parse command header
        if len(data) < 8:
            return None

        header = struct.unpack('<4H', data[:8])
        command = header[0]
        checksum = header[1]
        session_id = header[2]
        reply_id = header[3]

        self.session_id = session_id
        self.reply_id = reply_id

        command_string = data[8:]

        # Verify checksum
        calc_checksum = calculate_checksum(data[:8] + command_string)
        # Note: we don't strictly verify checksum in emulator

        # Handle command
        response_code, response_data = self._handle_command(command, command_string)

        # Create response
        response = self._create_response(response_code, response_code == CMD_ACK_OK, response_data, session_id, reply_id)

        # Add TCP header if needed
        if self.tcp_mode:
            response = self._create_tcp_top(response)

        return response


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle client connection"""
    addr = writer.get_extra_info('peername')
    print(f"Client connected: {addr}")

    emulator = ZKEmulator()
    buffer = b''

    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break

            buffer += data

            # Process complete packets
            while True:
                if len(buffer) < 8:
                    break

                # Check for TCP header
                if len(buffer) >= 8:
                    tcp_header = struct.unpack('<HHI', buffer[:8])
                    if tcp_header[0] == MACHINE_PREPARE_DATA_1 and tcp_header[1] == MACHINE_PREPARE_DATA_2:
                        expected_len = tcp_header[2]
                        if len(buffer) < 8 + expected_len:
                            break  # Wait for more data
                        packet = buffer[:8 + expected_len]
                        buffer = buffer[8 + expected_len:]
                    else:
                        # UDP-like packet, assume full packet
                        if len(buffer) < 8:
                            break
                        packet = buffer[:1024]  # Max packet size
                        buffer = buffer[1024:]
                else:
                    break

                response = emulator._process_packet(packet)
                if response:
                    writer.write(response)
                    await writer.drain()

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        print(f"Client disconnected: {addr}")
        writer.close()
        await writer.wait_closed()


async def main():
    """Main entry point"""
    host = os.environ.get("ZK_EMULATOR_HOST", "0.0.0.0")
    port = int(os.environ.get("ZK_EMULATOR_PORT", "4370"))

    server = await asyncio.start_server(handle_client, host, port)
    addr = server.sockets[0].getsockname()
    print(f"ZKTeco Emulator listening on {addr[0]}:{addr[1]}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEmulator stopped")
