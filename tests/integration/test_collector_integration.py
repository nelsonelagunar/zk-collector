"""
Integration tests for AttendanceCollector with emulator
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.buffer.repository import BufferRepository
from src.core.config import Config
from src.zk.attendance import AttendanceRecord
from src.zk.client import ZKClient


class TestCollectorEmulatorIntegration:
    """Integration tests for collector polling against emulator"""

    @pytest.fixture
    def temp_db(self):
        """Temporary database for tests"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def buffer_repo(self, temp_db):
        """Buffer repository with temp DB"""
        return BufferRepository(temp_db, max_records=1000)

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = Mock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            'platform.url': 'http://test-platform:8000',
            'platform.api_key': 'test-key',
            'platform.tenant_id': 'test-tenant',
            'platform.timeout': 30,
            'platform.retry_attempts': 3,
            'buffer.db_path': '/tmp/test_buffer.db',
            'buffer.max_records': 1000,
            'poll_interval_seconds': 1,
            'sync_interval_seconds': 1,
            'health.heartbeat_interval': 300,
            'devices': [
                {'ip': '127.0.0.1', 'port': 4370, 'timeout': 5, 'password': 0, 'enabled': True}
            ]
        }.get(key, default)
        return config

    @pytest.mark.asyncio
    async def test_collector_polls_emulator_and_stores_in_buffer(self, buffer_repo):
        """Test full collector cycle: connect -> poll -> store in buffer"""
        from tests.integration.test_emulator_integration import _handle_client

        server = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port = server.sockets[0].getsockname()[1]

        try:
            # Use ZKClient directly with emulator
            client = ZKClient('127.0.0.1', port=port, timeout=5)

            # Override connect to use our mock
            with patch('src.zk.client.ZK') as mock_zk:
                mock_instance = Mock()
                mock_zk.return_value = mock_instance

                # Simulate successful connection
                mock_instance.connect.return_value = True

                # Mock attendance data matching emulator
                mock_attendance = Mock()
                mock_attendance.user_id = "1"
                mock_attendance.timestamp = datetime(2026, 3, 3, 8, 0, 0)
                mock_attendance.status = 0

                mock_instance.get_attendance.return_value = [mock_attendance]

                connected = client.connect(max_retries=1)
                assert connected

                # Get attendance
                records = client.get_attendance()
                assert records is not None
                assert len(records) == 1
                assert isinstance(records[0], AttendanceRecord)

                # Store in buffer
                count = buffer_repo.add_records(records)
                assert count == 1

                # Verify in buffer
                unsynced = buffer_repo.get_unsynced_records()
                assert len(unsynced) == 1
                assert unsynced[0]['user_id'] == "1"

                client.disconnect()

        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_collector_handles_multiple_devices(self, buffer_repo):
        """Test collector handling multiple emulator instances"""
        from tests.integration.test_emulator_integration import MockCollector, _handle_client

        # Start two emulators on different ports
        server1 = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port1 = server1.sockets[0].getsockname()[1]

        server2 = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port2 = server2.sockets[0].getsockname()[1]

        try:
            collector1 = MockCollector('127.0.0.1', port1)
            collector2 = MockCollector('127.0.0.1', port2)

            await collector1.connect()
            await collector2.connect()

            # Poll both
            records1 = await collector1.get_attendance()
            records2 = await collector2.get_attendance()

            await collector1.disconnect()
            await collector2.disconnect()

            # Both should have records
            assert len(records1) == 12
            assert len(records2) == 12

            # Store both in buffer
            buffer_repo.add_records([
                AttendanceRecord(
                    user_id=r['user_id'],
                    timestamp=r['timestamp'],
                    status=r['status'],
                    device_ip='127.0.0.1'
                ) for r in records1 + records2
            ])

            unsynced = buffer_repo.get_unsynced_records()
            assert len(unsynced) == 24

        finally:
            server1.close()
            await server1.wait_closed()
            server2.close()
            await server2.wait_closed()


class TestCollectorSyncIntegration:
    """Integration tests for collector sync with platform"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def buffer_repo(self, temp_db):
        return BufferRepository(temp_db, max_records=1000)

    def test_sync_flow_with_mocked_platform(self, buffer_repo):
        """Test full sync flow with mocked HTTP responses"""
        from src.sync.platform import PlatformSync

        # Add test records to buffer
        records = [
            AttendanceRecord(
                user_id="1",
                timestamp=datetime(2026, 3, 3, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101"
            ),
            AttendanceRecord(
                user_id="2",
                timestamp=datetime(2026, 3, 3, 17, 0, 0),
                status=1,
                device_ip="192.168.1.101"
            )
        ]
        buffer_repo.add_records(records)

        # Mock platform sync
        with patch('src.sync.platform.PlatformSync.sync_attendance') as mock_sync:
            mock_sync.return_value = True

            platform_sync = PlatformSync(
                platform_url='http://test-platform:8000',
                api_key='test-key',
                tenant_id='test-tenant',
                timeout=30,
                retry_attempts=3
            )

            # Get unsynced
            unsynced = buffer_repo.get_unsynced_records()
            assert len(unsynced) == 2

            # Sync
            success = platform_sync.sync_attendance(unsynced)
            assert success

            # Mark synced
            record_ids = [r['id'] for r in unsynced]
            buffer_repo.mark_as_synced(record_ids)

            # Verify
            unsynced_after = buffer_repo.get_unsynced_records()
            assert len(unsynced_after) == 0

            stats = buffer_repo.get_stats()
            assert stats['synced'] == 2
            assert stats['pending_sync'] == 0


class TestCollectorEndToEnd:
    """End-to-end integration tests"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def buffer_repo(self, temp_db):
        return BufferRepository(temp_db, max_records=1000)

    @pytest.mark.asyncio
    async def test_full_poll_sync_cycle(self, buffer_repo):
        """Test complete poll -> buffer -> sync cycle"""
        from src.sync.platform import PlatformSync
        from tests.integration.test_emulator_integration import _handle_client

        server = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port = server.sockets[0].getsockname()[1]

        try:
            # 1. Poll from emulator using MockCollector
            from tests.integration.test_emulator_integration import MockCollector
            collector = MockCollector('127.0.0.1', port)
            await collector.connect()

            await collector.disable_device()
            records = await collector.get_attendance()
            await collector.enable_device()
            await collector.disconnect()

            # 2. Convert to AttendanceRecord and store in buffer
            attendance_records = [
                AttendanceRecord(
                    user_id=r['user_id'],
                    timestamp=r['timestamp'],
                    status=r['status'],
                    device_ip='127.0.0.1'
                ) for r in records
            ]
            buffer_repo.add_records(attendance_records)

            # 3. Verify buffer has records
            unsynced = buffer_repo.get_unsynced_records()
            assert len(unsynced) == 12  # From seed file

            # 4. Sync with mocked platform
            with patch('src.sync.platform.PlatformSync.sync_attendance') as mock_sync:
                mock_sync.return_value = True

                platform_sync = PlatformSync(
                    platform_url='http://test-platform:8000',
                    api_key='test-key',
                    tenant_id='test-tenant'
                )

                success = platform_sync.sync_attendance(unsynced)
                assert success

                record_ids = [r['id'] for r in unsynced]
                buffer_repo.mark_as_synced(record_ids)

            # 5. Verify all synced
            stats = buffer_repo.get_stats()
            assert stats['total_records'] == 12
            assert stats['pending_sync'] == 0
            assert stats['synced'] == 12

        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_buffer_cleanup_after_sync(self, buffer_repo):
        """Test that old synced records are cleaned up"""
        from tests.integration.test_emulator_integration import _handle_client

        server = await asyncio.start_server(
            lambda r, w: asyncio.create_task(_handle_client(r, w)), '127.0.0.1', 0
        )
        port = server.sockets[0].getsockname()[1]

        try:
            from tests.integration.test_emulator_integration import MockCollector
            collector = MockCollector('127.0.0.1', port)
            await collector.connect()

            await collector.disable_device()
            records = await collector.get_attendance()
            await collector.enable_device()
            await collector.disconnect()

            # Add many records
            for _ in range(5):
                attendance_records = [
                    AttendanceRecord(
                        user_id=r['user_id'],
                        timestamp=r['timestamp'],
                        status=r['status'],
                        device_ip='127.0.0.1'
                    ) for r in records
                ]
                buffer_repo.add_records(attendance_records)

            stats = buffer_repo.get_stats()
            assert stats['total_records'] == 60  # 12 * 5

            # Sync all
            unsynced = buffer_repo.get_unsynced_records()
            record_ids = [r['id'] for r in unsynced]
            buffer_repo.mark_as_synced(record_ids)

            stats = buffer_repo.get_stats()
            assert stats['synced'] == 60
            assert stats['pending_sync'] == 0

        finally:
            server.close()
            await server.wait_closed()
