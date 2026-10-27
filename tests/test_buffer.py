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
        ts = datetime(2026, 10, 13, 8, 0, 0)
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
                user_id=f"s{i}",
                timestamp=old_ts + timedelta(hours=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(60)
        ]
        pending_records = [
            AttendanceRecordDB(
                user_id=f"p{i}",
                timestamp=new_ts + timedelta(hours=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
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
                    user_id="extra",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
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
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada",
        )
        temp_db.add_records([old])
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        # Nuevas marcas deben NO purgar al veterano de 40 días
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="nuevo",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
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
                user_id=f"u{i}",
                timestamp=base + timedelta(seconds=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
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

    def test_manual_purge_synced_older_than(self, temp_db, tmp_path):
        """MYK-419/428: purge manual solo sync>days, con export previo y bitácora"""
        now = datetime.now()
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="viejo_sync",
                    timestamp=now - timedelta(days=800),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                ),
                AttendanceRecordDB(
                    user_id="reciente_sync",
                    timestamp=now - timedelta(days=100),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                ),
                AttendanceRecordDB(
                    user_id="viejo_pendiente",
                    timestamp=now - timedelta(days=800),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                ),
            ]
        )
        unsynced = temp_db.get_unsynced_records()
        ids = {r["user_id"]: r["id"] for r in unsynced}
        temp_db.mark_as_synced([ids["viejo_sync"], ids["reciente_sync"]])

        export = tmp_path / "exports" / "purge.json"
        deleted = temp_db.purge_synced_older_than(
            days=730,
            reason="purga anual auditada",
            operator="dba",
            export_path=str(export),
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
        # MYK-428: exportación previa verificada y evidenciada en bitácora
        assert audit[0]["export_path"] == str(export)
        assert export.exists()
        import json

        with open(export, encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["count"] == 1
        assert payload["records"][0]["user_id"] == "viejo_sync"

    def test_manual_purge_requires_reason_and_operator(self, temp_db, tmp_path):
        """MYK-419/428: sin reason/operator/export no hay borrado manual"""
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="x",
                    timestamp=datetime.now() - timedelta(days=999),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        export = str(tmp_path / "purge.json")
        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="", operator="dba", export_path=export)
        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="ok", operator="", export_path=export)
        # MYK-428: exportación previa OBLIGATORIA
        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="ok", operator="dba")
        assert temp_db.get_stats()["total_records"] == 1
        assert temp_db.get_retention_audit() == []

    def test_purge_aborts_when_export_fails(self, temp_db, tmp_path):
        """MYK-428 AC2: si la exportación falla, la purga NO borra nada"""
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="v",
                    timestamp=datetime.now() - timedelta(days=800),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        # La ruta de export cruza un archivo (no un directorio) -> OSError
        blocker = tmp_path / "blocker"
        blocker.write_text("no soy un directorio")
        with pytest.raises(OSError):
            temp_db.purge_synced_older_than(
                days=730,
                reason="ok",
                operator="dba",
                export_path=str(blocker / "sub" / "purge.json"),
            )
        assert temp_db.get_stats()["total_records"] == 1
        assert temp_db.get_retention_audit() == []

    def test_failed_records_kept_not_fake_synced(self, temp_db):
        """MYK-428: tras max intentos queda sync_failed=1 (NUNCA synced=1)"""
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="f",
                    timestamp=datetime.now() - timedelta(days=10),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )
        rid = temp_db.get_unsynced_records()[0]["id"]

        for _ in range(5):
            temp_db.mark_sync_failed([rid], max_attempts=5)

        # Fuera de la cola de sync (no reintenta en bucle)...
        assert temp_db.get_unsynced_records() == []
        # ...pero VIVO, consultable y contabilizado como fallido
        failed = temp_db.get_failed_records()
        assert len(failed) == 1
        assert failed[0]["sync_attempts"] == 5
        stats = temp_db.get_stats()
        assert stats["failed_sync"] == 1
        assert stats["pending_sync"] == 0
        assert stats["synced"] == 0
        with temp_db.get_connection() as conn:
            row = conn.execute(
                "SELECT synced, sync_failed FROM attendance_records WHERE id = ?",
                (rid,),
            ).fetchone()
        assert row["synced"] == 0
        assert row["sync_failed"] == 1

    def test_failed_records_never_archived_on_overflow(self, temp_db):
        """MYK-428: el overflow no archiva ni borra registros fallidos"""
        base = datetime.now() - timedelta(days=100)
        records = [
            AttendanceRecordDB(
                user_id=f"u{i}",
                timestamp=base + timedelta(seconds=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(99)
        ]
        temp_db.add_records(records)
        rid = temp_db.get_unsynced_records()[0]["id"]
        for _ in range(5):
            temp_db.mark_sync_failed([rid], max_attempts=5)

        # Forzar overflow: nada es synced -> ni fallidos ni pendientes se tocan
        temp_db.max_records = 50
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="extra",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )

        stats = temp_db.get_stats()
        assert stats["total_records"] == 100  # nada compactado: nada elegible
        assert stats["archived_records"] == 0
        assert stats["failed_sync"] == 1
        assert len(temp_db.get_failed_records()) == 1

    def test_capacity_overflow_archives_synced(self, temp_db):
        """MYK-428: overflow ARCHIVA synced viejos (no los borra)"""
        old_ts = datetime.now() - timedelta(days=100)
        synced = [
            AttendanceRecordDB(
                user_id=f"s{i}",
                timestamp=old_ts + timedelta(hours=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(20)
        ]
        pending = [
            AttendanceRecordDB(
                user_id=f"p{i}",
                timestamp=datetime.now() - timedelta(days=1),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(10)
        ]
        temp_db.add_records(synced + pending)
        unsynced = temp_db.get_unsynced_records(limit=1000)
        temp_db.mark_as_synced([r["id"] for r in unsynced[:20]])

        temp_db.max_records = 30
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="extra",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )

        stats = temp_db.get_stats()
        # 31 registros, max 30: 1 synced archivado, cero borrados
        assert stats["total_records"] == 30
        assert stats["archived_records"] == 1
        assert stats["pending_sync"] == 11
        archived = temp_db.get_archived_records()
        assert len(archived) == 1
        assert archived[0]["source_id"] is not None
        assert archived[0]["archive_reason"] == "capacity_overflow"
        audit = temp_db.get_retention_audit()
        assert audit[0]["action"] == "archive_overflow"

    def test_purge_archived_requires_export_and_only_touches_archive(self, temp_db, tmp_path):
        """MYK-428: purga conformante = solo archivados, export previo"""
        old_ts = datetime.now() - timedelta(days=800)
        synced = [
            AttendanceRecordDB(
                user_id=f"s{i}",
                timestamp=old_ts + timedelta(hours=i),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada",
            )
            for i in range(3)
        ]
        temp_db.add_records(synced)
        temp_db.mark_as_synced([r["id"] for r in temp_db.get_unsynced_records()])
        # Forzar archive: bajar max_records y re-agregar dispara _enforce_capacity
        temp_db.max_records = 2
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="nuevo",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada",
                )
            ]
        )
        assert temp_db.get_stats()["archived_records"] == 2

        with pytest.raises(ValueError):
            temp_db.purge_archived_older_than(days=730, reason="ok", operator="dba")

        export = tmp_path / "archived_purge.json"
        deleted = temp_db.purge_archived_older_than(
            days=730,
            reason="purga archivados",
            operator="dba",
            export_path=str(export),
        )
        assert deleted == 2
        assert temp_db.get_archived_records() == []
        audit = temp_db.get_retention_audit()
        purge_rows = [a for a in audit if a["action"] == "purge_archived"]
        assert purge_rows[0]["records_deleted"] == 2
        assert purge_rows[0]["export_path"] == str(export)
        assert export.exists()
        import json

        with open(export, encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["count"] == 2

    def test_log_sync(self, temp_db):
        """Test de log de sincronización"""
        temp_db.log_sync(
            records_synced=10, records_failed=0, status="success", duration_seconds=1.5
        )

        history = temp_db.get_sync_history()

        assert len(history) == 1
        assert history[0]["records_synced"] == 10
        assert history[0]["status"] == "success"
