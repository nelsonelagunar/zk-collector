"""
Tests para el módulo Buffer
"""

from datetime import datetime, timedelta

import pytest

from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository


class TestBufferRepository:
    """Tests para BufferRepository"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Base de datos temporal para tests"""
        db_path = tmp_path / "test_buffer.db"
        return BufferRepository(db_path, max_records=100)

    def test_init(self, temp_db, tmp_path):
        """Test de inicialización"""
        assert temp_db.db_path == tmp_path / "test_buffer.db"
        assert temp_db.max_records == 100
        assert temp_db.db_path.exists()

    def test_add_records(self, temp_db):
        """Test de agregar registros"""
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            ),
            AttendanceRecordDB(
                user_id="2",
                timestamp=datetime.now(),
                status=1,
                device_ip="192.168.1.101",
                punch_type="salida",
            ),
        ]

        count = temp_db.add_records(records)

        assert count == 2

    def test_add_records_deduplicates(self, temp_db):
        """El log completo del device en polls repetidos no debe duplicar filas"""
        ts = datetime.now()
        records = [
            AttendanceRecordDB(
                user_id="1", timestamp=ts, status=0, device_ip="10.0.0.12", punch_type="entrada"
            ),
            AttendanceRecordDB(
                user_id="2", timestamp=ts, status=1, device_ip="10.0.0.12", punch_type="salida"
            ),
        ]

        assert temp_db.add_records(records) == 2
        # Un segundo poll devuelve el mismo log -> 0 registros nuevos
        assert temp_db.add_records(records) == 0
        assert temp_db.get_stats()["total_records"] == 2

    def test_get_unsynced_records(self, temp_db):
        """Test de obtención de registros sin sincronizar"""
        # Agregar registro
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
        ]
        temp_db.add_records(records)

        # Obtener no sincronizados
        unsynced = temp_db.get_unsynced_records()

        assert len(unsynced) == 1
        assert unsynced[0]["user_id"] == "1"

    def test_mark_as_synced(self, temp_db):
        """Test de marcar registros como sincronizados"""
        # Agregar registro
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
        ]
        temp_db.add_records(records)

        # Obtener ID
        unsynced = temp_db.get_unsynced_records()
        record_id = unsynced[0]["id"]

        # Marcar como sincronizado
        updated = temp_db.mark_as_synced([record_id])

        assert updated == 1

        # Verificar
        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 0

    def test_get_stats(self, temp_db):
        """Test de obtención de estadísticas"""
        # Agregar algunos registros
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
        ]
        temp_db.add_records(records)

        stats = temp_db.get_stats()

        assert stats["total_records"] == 1
        assert stats["pending_sync"] == 1
        assert stats["synced"] == 0

    def test_capacity_compacts_synced_only(self, temp_db):
        """MYK-419: el overflow compacta SOLO sincronizados; pendientes intactos"""
        old_ts = datetime.now() - timedelta(days=100)
        new_ts = datetime.now() - timedelta(days=1)

        synced_records = [
            AttendanceRecordDB(
                user_id=f"s{i}", timestamp=old_ts + timedelta(hours=i),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            )
            for i in range(60)
        ]
        pending_records = [
            AttendanceRecordDB(
                user_id=f"p{i}", timestamp=new_ts + timedelta(hours=i),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            )
            for i in range(50)
        ]
        temp_db.add_records(synced_records + pending_records)

        # Los 60 más antiguos (s*) se marcan como sincronizados
        unsynced = temp_db.get_unsynced_records(limit=1000)
        assert len(unsynced) == 110
        temp_db.mark_as_synced([r["id"] for r in unsynced[:60]])

        # Un registro más dispara el overflow (111 > max_records=100)
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="extra", timestamp=datetime.now(),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                )
            ]
        )

        stats = temp_db.get_stats()
        # Se compactaron 11 sincronizados; los 51 pendientes NINGUNO se perdió
        assert stats["total_records"] == 100
        assert stats["pending_sync"] == 51
        assert stats["synced"] == 49

    def test_synced_40_days_not_purged(self, temp_db):
        """MYK-419 AC: registro sync'd de 40 días NO se borra (fin del purge a 30d)"""
        old = AttendanceRecordDB(
            user_id="veterano",
            timestamp=datetime.now() - timedelta(days=40),
            status=0, device_ip="192.168.1.101", punch_type="entrada",
        )
        temp_db.add_records([old])
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        # Nuevas marcas deben NO purgar al veterano de 40 días
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="nuevo", timestamp=datetime.now(),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                )
            ]
        )

        with temp_db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE user_id = 'veterano'"
            ).fetchone()
        assert row[0] == 1

    def test_overflow_never_deletes_unsynced(self, tmp_path):
        """MYK-419 AC: overflow 10k+1 con pendientes -> ninguno perdido"""
        repo = BufferRepository(tmp_path / "overflow.db", max_records=10000)
        base = datetime.now() - timedelta(days=1)
        records = [
            AttendanceRecordDB(
                user_id=f"u{i}", timestamp=base + timedelta(seconds=i),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            )
            for i in range(10001)
        ]

        repo.add_records(records)

        stats = repo.get_stats()
        assert stats["total_records"] == 10001
        assert stats["pending_sync"] == 10001
        # Ningún pendiente perdido pese a exceder max_records en 1
        unsynced = repo.get_unsynced_records(limit=20000)
        assert len(unsynced) == 10001

    def test_manual_purge_synced_older_than(self, temp_db):
        """MYK-419: purge manual solo sync>days, con bitácora obligatoria"""
        now = datetime.now()
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="viejo_sync", timestamp=now - timedelta(days=800),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                ),
                AttendanceRecordDB(
                    user_id="reciente_sync", timestamp=now - timedelta(days=100),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                ),
                AttendanceRecordDB(
                    user_id="viejo_pendiente", timestamp=now - timedelta(days=800),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                ),
            ]
        )
        unsynced = temp_db.get_unsynced_records()
        ids = {r["user_id"]: r["id"] for r in unsynced}
        temp_db.mark_as_synced([ids["viejo_sync"], ids["reciente_sync"]])

        deleted = temp_db.purge_synced_older_than(
            days=730, reason="purga anual auditada", operator="dba"
        )

        assert deleted == 1
        stats = temp_db.get_stats()
        assert stats["total_records"] == 2
        assert stats["pending_sync"] == 1  # viejo_pendiente sigue vivo

        audit = temp_db.get_retention_audit()
        assert len(audit) == 1
        assert audit[0]["action"] == "purge_synced"
        assert audit[0]["records_deleted"] == 1
        assert audit[0]["operator"] == "dba"
        assert "purga anual" in audit[0]["reason"]

    def test_manual_purge_requires_reason_and_operator(self, temp_db):
        """MYK-419: sin reason/operator no hay borrado manual (bitácora obligatoria)"""
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="x", timestamp=datetime.now() - timedelta(days=999),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                )
            ]
        )
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="", operator="dba")
        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="ok", operator="")
        assert temp_db.get_stats()["total_records"] == 1
        assert temp_db.get_retention_audit() == []

    def test_log_sync(self, temp_db):
        """Test de log de sincronización"""
        temp_db.log_sync(
            records_synced=10, records_failed=0, status="success", duration_seconds=1.5
        )

        history = temp_db.get_sync_history()

        assert len(history) == 1
        assert history[0]["records_synced"] == 10
        assert history[0]["status"] == "success"
