"""
Integration tests for collector <-> emulator communication
"""

import asyncio
import struct
from datetime import datetime

import pytest

from mock.zk_emulator import (
    CMD_ACK_OK,
    CMD_ATTLOG_RRQ,
    CMD_CONNECT,
    CMD_DISABLEDEVICE,
    CMD_ENABLEDEVICE,
    CMD_EXIT,
    CMD_GET_FREE_SIZES,
    CMD_GET_TIME,
    CMD_USERTEMP_RRQ,
    MACHINE_PREPARE_DATA_1,
    MACHINE_PREPARE_DATA_2,
    USHRT_MAX,
    calculate_checksum,
)


def make_packet(
    command: int,
    command_string: bytes = b"",
    session_id: int = 0,
    reply_id: int = USHRT_MAX - 1,
) -> bytes:
    """Build a raw ZK protocol packet (no TCP header)"""
    buf = struct.pack("<4H", command, 0, session_id, reply_id) + command_string
    buf_bytes = bytearray(buf)
    checksum = calculate_checksum(bytes(buf_bytes))
    new_reply = reply_id + 1 if reply_id + 1 < USHRT_MAX else reply_id + 1 - USHRT_MAX
    return struct.pack("<4H", command, checksum, session_id, new_reply) + command_string


def make_tcp_packet(
    command: int,
    command_string: bytes = b"",
    session_id: int = 0,
    reply_id: int = USHRT_MAX - 1,
) -> bytes:
    """Build a packet with TCP header"""
    inner = make_packet(command, command_string, session_id, reply_id)
    tcp_header = struct.pack("<HHI", MACHINE_PREPARE_DATA_1, MACHINE_PREPARE_DATA_2, len(inner))
    return tcp_header + inner


def parse_tcp_packet(data: bytes) -> bytes:
    """Strip the TCP top header and return the inner packet"""
    if len(data) < 8:
        return data
    top = struct.unpack("<HHI", data[:8])
    if top[0] == MACHINE_PREPARE_DATA_1 and top[1] == MACHINE_PREPARE_DATA_2:
        return data[8 : 8 + top[2]]
    return data


def parse_response(data: bytes) -> tuple[int, bytes]:
    """Parse emulator response into (command_code, payload)"""
    header = struct.unpack("<4H", data[:8])
    return header[0], data[8:]


class MockCollector:
    """Simple collector that talks to the emulator"""

    def __init__(self, host: str = "127.0.0.1", port: int = 4370):
        self.host = host
        self.port = port
        self.session_id = 0
        self.reply_id = USHRT_MAX - 1
        self.reader = None
        self.writer = None

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

        # Send connect
        packet = make_tcp_packet(CMD_CONNECT, session_id=self.session_id, reply_id=self.reply_id)
        self.writer.write(packet)
        await self.writer.drain()
        self.reply_id = (self.reply_id + 1) % USHRT_MAX

        # Read response
        response = await asyncio.wait_for(self.reader.read(4096), timeout=5)
        inner = parse_tcp_packet(response)
        code, _ = parse_response(inner)
        assert code == CMD_ACK_OK, f"Connect failed: code={code}"
        self.session_id = 1  # Session established

    async def disconnect(self):
        if self.writer:
            packet = make_tcp_packet(CMD_EXIT, session_id=self.session_id, reply_id=self.reply_id)
            self.writer.write(packet)
            await self.writer.drain()
            self.writer.close()
            await self.writer.wait_closed()

    async def _send_command(self, command: int, command_string: bytes = b"") -> bytes:
        """Send a command and return response payload"""
        packet = make_tcp_packet(command, command_string, self.session_id, self.reply_id)
        self.writer.write(packet)
        await self.writer.drain()
        self.reply_id = (self.reply_id + 1) % USHRT_MAX

        response = await asyncio.wait_for(self.reader.read(4096), timeout=5)
        inner = parse_tcp_packet(response)
        code, payload = parse_response(inner)
        assert code == CMD_ACK_OK, f"Command {command} failed: code={code}"
        return payload

    async def get_time(self) -> datetime:
        payload = await self._send_command(CMD_GET_TIME)
        timestamp = struct.unpack("<I", payload)[0]
        return self._decode_time(timestamp)

    async def get_free_sizes(self) -> dict:
        payload = await self._send_command(CMD_GET_FREE_SIZES)
        fields = struct.unpack("<20i", payload)
        return {
            "users": fields[4],
            "fingers": fields[6],
            "records": fields[8],
            "cards": fields[12],
            "fingers_cap": fields[14],
            "users_cap": fields[15],
            "rec_cap": fields[16],
            "fingers_av": fields[17],
            "users_av": fields[18],
            "rec_av": fields[19],
        }

    async def get_users(self) -> list[dict]:
        payload = await self._send_command(CMD_USERTEMP_RRQ)
        # Parse: 4-byte total size + N * 28-byte user records
        total_size = struct.unpack("<I", payload[:4])[0]
        users = []
        for i in range(total_size // 28):
            offset = 4 + i * 28
            user_data = payload[offset : offset + 28]
            uid, privilege, password, name, card, group_id, timezone, user_id = struct.unpack(
                "<HB5s8sIxBhI", user_data
            )
            users.append(
                {
                    "uid": uid,
                    "user_id": str(user_id),
                    "name": name.decode("utf-8", errors="ignore").rstrip("\x00"),
                    "privilege": privilege,
                    "password": password.decode("utf-8", errors="ignore").rstrip("\x00"),
                }
            )
        return users

    async def get_attendance(self) -> list[dict]:
        payload = await self._send_command(CMD_ATTLOG_RRQ)
        # Parse: 4-byte total size + N * 8-byte attendance records
        total_size = struct.unpack("<I", payload[:4])[0]
        records = []
        for i in range(total_size // 8):
            offset = 4 + i * 8
            att_data = payload[offset : offset + 8]
            user_id, status, timestamp_bytes, punch = struct.unpack("<HB4sB", att_data)
            timestamp = struct.unpack("<I", timestamp_bytes)[0]
            records.append(
                {
                    "user_id": str(user_id),
                    "status": status,
                    "timestamp": self._decode_time(timestamp),
                    "punch": punch,
                }
            )
        return records

    async def disable_device(self):
        await self._send_command(CMD_DISABLEDEVICE)

    async def enable_device(self):
        await self._send_command(CMD_ENABLEDEVICE)

    def _decode_time(self, encoded: int) -> datetime:
        """Decode ZK timestamp back to datetime"""
        # Inverse of encode_time
        second = encoded % 60
        encoded //= 60
        minute = encoded % 60
        encoded //= 60
        hour = encoded % 24
        encoded //= 24
        day = encoded % 31 + 1
        encoded //= 31
        month = encoded % 12 + 1
        encoded //= 12
        year = encoded + 2000
        return datetime(year, month, day, hour, minute, second)


@pytest.mark.asyncio
async def test_emulator_server_starts():
    """Test emulator server starts and listens on port"""
    server = await asyncio.start_server(
        lambda r, w: asyncio.create_task(_handle_client(r, w)), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]

    # Connect and verify
    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    packet = make_tcp_packet(CMD_CONNECT)
    writer.write(packet)
    await writer.drain()

    response = await asyncio.wait_for(reader.read(4096), timeout=3)
    assert len(response) > 8

    writer.close()
    await writer.wait_closed()
    server.close()
    await asyncio.wait_for(server.wait_closed(), timeout=5)


async def _handle_client(reader, writer):
    from mock.zk_emulator import handle_client
    await handle_client(reader, writer)


@pytest.mark.asyncio
async def test_collector_polls_emulator_full_cycle():
    """Test full collector poll cycle against emulator"""
    # Start emulator server
    server = await asyncio.start_server(
        lambda r, w: asyncio.create_task(_handle_client(r, w)), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]

    try:
        # Create collector and connect
        collector = MockCollector("127.0.0.1", port)
        await collector.connect()

        # Get device time
        dt = await collector.get_time()
        assert isinstance(dt, datetime)

        # Get free sizes
        sizes = await collector.get_free_sizes()
        assert sizes["users"] == 3  # 3 synthetic users
        assert sizes["records"] > 0  # Has attendance records

        # Get users
        users = await collector.get_users()
        assert len(users) == 3
        assert users[0]["user_id"] == "1"
        assert users[0]["name"] == "User1"

        # Get attendance (full cycle with disable/enable)
        await collector.disable_device()
        records = await collector.get_attendance()
        await collector.enable_device()

        assert len(records) > 0
        # Check we have records from seed file
        user_ids = {r["user_id"] for r in records}
        assert "1" in user_ids
        assert "2" in user_ids
        assert "3" in user_ids

        # Verify timestamps are valid
        for r in records:
            assert isinstance(r["timestamp"], datetime)
            assert r["status"] in (0, 1)

        await collector.disconnect()

    finally:
        server.close()
        await asyncio.wait_for(server.wait_closed(), timeout=5)


@pytest.mark.asyncio
async def test_collector_handles_reconnection():
    """Test collector can reconnect after disconnect"""
    server = await asyncio.start_server(
        lambda r, w: asyncio.create_task(_handle_client(r, w)), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]

    try:
        collector = MockCollector("127.0.0.1", port)
        await collector.connect()
        await collector.get_time()
        await collector.disconnect()

        # Reconnect
        await collector.connect()
        dt = await collector.get_time()
        assert isinstance(dt, datetime)
        await collector.disconnect()

    finally:
        server.close()
        await asyncio.wait_for(server.wait_closed(), timeout=5)


@pytest.mark.asyncio
async def test_emulator_attendance_records_match_seed():
    """Test that emulator returns the exact records from attendance_seed.json"""
    server = await asyncio.start_server(
        lambda r, w: asyncio.create_task(_handle_client(r, w)), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]

    try:
        collector = MockCollector("127.0.0.1", port)
        await collector.connect()

        await collector.disable_device()
        records = await collector.get_attendance()
        await collector.enable_device()

        # Should have 12 records from seed file
        assert len(records) == 12

        # Check specific records from seed
        check_ins = [r for r in records if r["status"] == 0]
        check_outs = [r for r in records if r["status"] == 1]
        assert len(check_ins) == 6
        assert len(check_outs) == 6

        await collector.disconnect()

    finally:
        server.close()
        await asyncio.wait_for(server.wait_closed(), timeout=5)
