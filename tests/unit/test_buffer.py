"""
Unit tests for BufferRepository module
"""

from datetime import datetime, timedelta

import pytest

from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing"""
    db_path = tmp_path / "test_buffer.db"
    return BufferRepository(db_path, max_records=100)


@pytest.fixture
def sample_records():
    """Create sample attendance records"""
    now = datetime.now()
    return [
        AttendanceRecordDB(
            user_id="1",
            timestamp=now - timedelta(days=2, hours=8),
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada",
        ),
        AttendanceRecordDB(
            user_id="2",
            timestamp=now - timedelta(days=2, hours=1),
            status=1,
            device_ip="192.168.1.101",
            punch_type="salida",
        ),
        AttendanceRecordDB(
            user_id="3",
            timestamp=now - timedelta(days=1, hours=8),
            status=0,
            device_ip="192.168.1.102",
            punch_type="entrada",
        ),
    ]


class TestBufferRepositoryInit:
    """Tests for BufferRepository initialization"""

    def test_init_creates_database(self, tmp_path):
        """Test initialization creates database file and tables"""
        db_path = tmp_path / "test.db"
        repo = BufferRepository(db_path, max_records=100)

        assert db_path.exists()
        assert repo.db_path == db_path
        assert repo.max_records == 100

    def test_init_creates_tables(self, temp_db):
        """Test that tables are created on init"""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check attendance_records table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_records'"
            )
            assert cursor.fetchone() is not None

            # Check sync_log table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_log'")
            assert cursor.fetchone() is not None

            # Check indexes
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synced'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_parent_directories(self, tmp_path):
        """Test initialization creates parent directories"""
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        repo = BufferRepository(db_path, max_records=100)

        assert db_path.exists()
        assert db_path.parent.exists()


class TestAddRecords:
    """Tests for add_records method"""

    def test_add_records_basic(self, temp_db, sample_records):
        """Test adding records to buffer"""
        count = temp_db.add_records(sample_records)
        assert count == 3

        # Verify records in database
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            assert cursor.fetchone()[0] == 3

    def test_add_records_empty_list(self, temp_db):
        """Test adding empty list returns 0"""
        count = temp_db.add_records([])
        assert count == 0

    def test_add_records_preserves_data(self, temp_db, sample_records):
        """Test added records preserve all fields"""
        temp_db.add_records(sample_records)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, timestamp, status, device_ip, punch_type, synced FROM attendance_records ORDER BY id"
            )
            rows = cursor.fetchall()

            assert len(rows) == 3
            assert rows[0]["user_id"] == "1"
            assert rows[0]["status"] == 0
            assert rows[0]["device_ip"] == "192.168.1.101"
            assert rows[0]["punch_type"] == "entrada"
            assert rows[0]["synced"] == 0  # Default

            assert rows[1]["user_id"] == "2"
            assert rows[1]["status"] == 1
            assert rows[1]["punch_type"] == "salida"

            assert rows[2]["user_id"] == "3"
            assert rows[2]["device_ip"] == "192.168.1.102"

    def test_add_records_batch_insert(self, temp_db):
        """Test that records are inserted in batch"""
        records = [
            AttendanceRecordDB(
                user_id=str(i),
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(50)
        ]

        count = temp_db.add_records(records)
        assert count == 50

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            assert cursor.fetchone()[0] == 50


class TestGetUnsyncedRecords:
    """Tests for get_unsynced_records method"""

    def test_get_unsynced_records(self, temp_db, sample_records):
        """Test getting unsynced records"""
        temp_db.add_records(sample_records)

        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 3
        assert all(r["synced"] == 0 for r in unsynced)

    def test_get_unsynced_records_limit(self, temp_db, sample_records):
        """Test limit parameter"""
        temp_db.add_records(sample_records)

        unsynced = temp_db.get_unsynced_records(limit=2)
        assert len(unsynced) == 2

    def test_get_unsynced_records_ordered(self, temp_db, sample_records):
        """Test records are ordered by timestamp then id"""
        temp_db.add_records(sample_records)

        unsynced = temp_db.get_unsynced_records()
        # Should be ordered by timestamp ASC, then id ASC
        assert unsynced[0]["user_id"] == "1"  # 8:00
        assert unsynced[1]["user_id"] == "2"  # 17:00
        assert unsynced[2]["user_id"] == "3"  # Next day 8:00

    def test_get_unsynced_after_mark_synced(self, temp_db, sample_records):
        """Test get_unsynced excludes synced records"""
        temp_db.add_records(sample_records)

        # Mark first two as synced
        unsynced = temp_db.get_unsynced_records()
        temp_db.mark_as_synced([unsynced[0]["id"], unsynced[1]["id"]])

        remaining = temp_db.get_unsynced_records()
        assert len(remaining) == 1
        assert remaining[0]["user_id"] == "3"


class TestMarkAsSynced:
    """Tests for mark_as_synced method"""

    def test_mark_as_synced(self, temp_db, sample_records):
        """Test marking records as synced"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        updated = temp_db.mark_as_synced([unsynced[0]["id"]])
        assert updated == 1

        # Verify in database
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT synced FROM attendance_records WHERE id = ?", (unsynced[0]["id"],)
            )
            assert cursor.fetchone()[0] == 1

    def test_mark_as_synced_multiple(self, temp_db, sample_records):
        """Test marking multiple records as synced"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        ids = [r["id"] for r in unsynced[:2]]
        updated = temp_db.mark_as_synced(ids)
        assert updated == 2

    def test_mark_as_synced_empty_list(self, temp_db):
        """Test marking empty list returns 0"""
        updated = temp_db.mark_as_synced([])
        assert updated == 0

    def test_mark_as_synced_nonexistent_id(self, temp_db, sample_records):
        """Test marking nonexistent ID doesn't error"""
        temp_db.add_records(sample_records)

        updated = temp_db.mark_as_synced([99999])  # Non-existent ID
        assert updated == 0


class TestMarkSyncFailed:
    """Tests for mark_sync_failed method"""

    def test_mark_sync_failed_increments_attempts(self, temp_db, sample_records):
        """Test sync_attempts is incremented"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        temp_db.mark_sync_failed([unsynced[0]["id"]])

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sync_attempts FROM attendance_records WHERE id = ?", (unsynced[0]["id"],)
            )
            assert cursor.fetchone()[0] == 1

    def test_mark_sync_failed_multiple_increments(self, temp_db, sample_records):
        """Test multiple failures increment attempts"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        temp_db.mark_sync_failed([unsynced[0]["id"]], max_attempts=5)
        temp_db.mark_sync_failed([unsynced[0]["id"]], max_attempts=5)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sync_attempts FROM attendance_records WHERE id = ?", (unsynced[0]["id"],)
            )
            assert cursor.fetchone()[0] == 2

    def test_mark_sync_failed_marks_synced_after_max_attempts(self, temp_db, sample_records):
        """Test record marked as synced after max attempts exceeded"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        # Fail max_attempts times (default 5)
        for _ in range(5):
            temp_db.mark_sync_failed([unsynced[0]["id"]], max_attempts=5)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT synced FROM attendance_records WHERE id = ?", (unsynced[0]["id"],)
            )
            assert cursor.fetchone()[0] == 1  # Marked as synced (discarded)


class TestCleanupOldRecords:
    """Tests for _cleanup_old_records method"""

    def test_cleanup_old_synced_records(self, temp_db, sample_records):
        """Test cleanup removes old synced records"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()

        # Mark all as synced
        temp_db.mark_as_synced([r["id"] for r in unsynced])

        # Manually update timestamps to be old
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            old_date = (datetime.now() - timedelta(days=60)).isoformat()
            cursor.execute("UPDATE attendance_records SET timestamp = ?", (old_date,))

        # Run cleanup with 30 days retention
        temp_db._cleanup_old_records(days=30)

        stats = temp_db.get_stats()
        assert stats["total_records"] == 0

    def test_cleanup_keeps_recent_records(self, temp_db, sample_records):
        """Test cleanup keeps recent records"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()
        temp_db.mark_as_synced([r["id"] for r in unsynced])

        # Run cleanup with 30 days retention (records are recent)
        temp_db._cleanup_old_records(days=30)

        stats = temp_db.get_stats()
        assert stats["total_records"] == 3

    def test_cleanup_unsynced_records_not_removed(self, temp_db, sample_records):
        """Test cleanup doesn't remove unsynced records"""
        temp_db.add_records(sample_records)

        # Make timestamps old but keep unsynced
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            old_date = (datetime.now() - timedelta(days=60)).isoformat()
            cursor.execute("UPDATE attendance_records SET timestamp = ?", (old_date,))

        temp_db._cleanup_old_records(days=30)

        stats = temp_db.get_stats()
        assert stats["total_records"] == 3  # Unsynced kept
        assert stats["pending_sync"] == 3


class TestMaxRecordsCleanup:
    """Tests for max_records limit enforcement"""

    def test_cleanup_exceeds_max_records(self, temp_db):
        """Test cleanup when exceeding max_records"""
        temp_db.max_records = 5

        # Add 10 records
        records = [
            AttendanceRecordDB(
                user_id=str(i),
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(10)
        ]
        temp_db.add_records(records)

        stats = temp_db.get_stats()
        assert stats["total_records"] <= 5

    def test_cleanup_keeps_newest(self, temp_db):
        """Test cleanup keeps newest records when exceeding max"""
        temp_db.max_records = 3

        # Add 5 records with different timestamps
        base_time = datetime(2026, 3, 3, 8, 0, 0)
        records = [
            AttendanceRecordDB(
                user_id=str(i),
                timestamp=base_time + timedelta(hours=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(5)
        ]
        temp_db.add_records(records)

        stats = temp_db.get_stats()
        assert stats["total_records"] == 3

        # Should keep the 3 newest (highest timestamps)
        unsynced = temp_db.get_unsynced_records()
        user_ids = [r["user_id"] for r in unsynced]
        assert "4" in user_ids  # Latest
        assert "3" in user_ids
        assert "2" in user_ids


class TestGetStats:
    """Tests for get_stats method"""

    def test_get_stats_empty(self, temp_db):
        """Test stats on empty buffer"""
        stats = temp_db.get_stats()
        assert stats["total_records"] == 0
        assert stats["pending_sync"] == 0
        assert stats["synced"] == 0
        assert stats["oldest_pending"] is None
        assert stats["newest_record"] is None
        assert stats["max_records"] == 100
        assert stats["usage_percent"] == 0

    def test_get_stats_with_records(self, temp_db, sample_records):
        """Test stats with records"""
        temp_db.add_records(sample_records)

        stats = temp_db.get_stats()
        assert stats["total_records"] == 3
        assert stats["pending_sync"] == 3
        assert stats["synced"] == 0
        assert stats["oldest_pending"] is not None
        assert stats["newest_record"] is not None
        assert stats["usage_percent"] == 3.0  # 3/100 * 100

    def test_get_stats_after_sync(self, temp_db, sample_records):
        """Test stats after marking synced"""
        temp_db.add_records(sample_records)
        unsynced = temp_db.get_unsynced_records()
        temp_db.mark_as_synced([unsynced[0]["id"]])

        stats = temp_db.get_stats()
        assert stats["total_records"] == 3
        assert stats["pending_sync"] == 2
        assert stats["synced"] == 1


class TestSyncLog:
    """Tests for sync logging"""

    def test_log_sync(self, temp_db):
        """Test logging sync operation"""
        temp_db.log_sync(
            records_synced=10, records_failed=0, status="success", duration_seconds=1.5
        )

        history = temp_db.get_sync_history()
        assert len(history) == 1
        assert history[0]["records_synced"] == 10
        assert history[0]["records_failed"] == 0
        assert history[0]["status"] == "success"
        assert history[0]["duration_seconds"] == 1.5

    def test_log_sync_failed(self, temp_db):
        """Test logging failed sync"""
        temp_db.log_sync(
            records_synced=0,
            records_failed=5,
            status="failed",
            error_message="Connection timeout",
            duration_seconds=30.0,
        )

        history = temp_db.get_sync_history()
        assert len(history) == 1
        assert history[0]["records_synced"] == 0
        assert history[0]["records_failed"] == 5
        assert history[0]["status"] == "failed"
        assert history[0]["error_message"] == "Connection timeout"

    def test_get_sync_history_limit(self, temp_db):
        """Test sync history limit"""
        from datetime import datetime, timedelta

        base_time = datetime.now()
        for i in range(60):
            # Insert with explicit timestamps to ensure ordering
            with temp_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO sync_log 
                    (records_synced, records_failed, status, error_message, duration_seconds, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (i, 0, "success", None, 1.0, (base_time + timedelta(seconds=i)).isoformat()),
                )

        history = temp_db.get_sync_history(limit=50)
        assert len(history) == 50

        # Should be ordered by timestamp DESC (newest first)
        assert history[0]["records_synced"] == 59
        assert history[49]["records_synced"] == 10


class TestClearAll:
    """Tests for clear_all method"""

    def test_clear_all(self, temp_db, sample_records):
        """Test clearing all records"""
        temp_db.add_records(sample_records)
        temp_db.log_sync(3, 0, "success", 1.0)

        temp_db.clear_all()

        stats = temp_db.get_stats()
        assert stats["total_records"] == 0
        assert stats["pending_sync"] == 0

        history = temp_db.get_sync_history()
        assert len(history) == 0


class TestConcurrency:
    """Tests for thread safety"""

    def test_concurrent_add_records(self, temp_db):
        """Test concurrent add_records operations"""
        import threading

        errors = []

        def add_batch(batch_id):
            try:
                records = [
                    AttendanceRecordDB(
                        user_id=f"{batch_id}-{i}",
                        timestamp=datetime.now(),
                        status=0,
                        device_ip="192.168.1.101",
                        punch_type="entrada",
                    )
                    for i in range(10)
                ]
                temp_db.add_records(records)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_batch, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = temp_db.get_stats()
        assert stats["total_records"] == 100

    def test_concurrent_get_and_mark(self, temp_db, sample_records):
        """Test concurrent get and mark operations"""
        import threading

        temp_db.add_records(sample_records)
        errors = []

        def get_and_mark():
            try:
                unsynced = temp_db.get_unsynced_records()
                if unsynced:
                    temp_db.mark_as_synced([unsynced[0]["id"]])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_and_mark) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = temp_db.get_stats()
        assert stats["total_records"] == 3
