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
        """Base de datos temporal para tests (sin archive_dir: no se borra nada)"""
        db_path = tmp_path / "test_buffer.db"
        return BufferRepository(db_path, max_records=100)

    @pytest.fixture
    def temp_db_archive(self, tmp_path):
        """Base de datos temporal con archive_dir habilitado (archive-and-purge)"""
        db_path = tmp_path / "test_buffer.db"
        archive_dir = tmp_path / "archive"
        return BufferRepository(db_path, max_records=100, archive_dir=archive_dir)

    def test_init(self, temp_db, tmp_path):
        """Test de inicialización"""
        assert temp_db.db_path == tmp_path / "test_buffer.db"
        assert temp_db.max_records == 100
        assert temp_db.db_path.exists()
        assert temp_db.retention_days == 790  # RT-1: default 26 meses (~790 días)

    def test_init_with_retention_days(self, tmp_path):
        """retention_days configurable"""
        repo = BufferRepository(tmp_path / "r.db", retention_days=500)
        assert repo.retention_days == 500

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
        assert stats["retention_days"] == 790

    def test_capacity_compacts_synced_only(self, temp_db):
        """MYK-419: el overflow compacta SOLO sincronizados; pendientes intactos.
        Con archive_dir=None no se borra nada (archive-and-purge requiere
        export previa); se registra aviso crítico.
        """
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
        # Sin archive_dir no se borra nada: se conservan los 111 registros
        temp_db.add_records(
            [
                AttendanceRecordDB(
                    user_id="extra", timestamp=datetime.now(),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                )
            ]
        )

        stats = temp_db.get_stats()
        # Nada se borró (sin archive_dir): 111 registros, 51 pendientes intactos
        assert stats["total_records"] == 111
        assert stats["pending_sync"] == 51

    def test_capacity_archive_and_purge(self, temp_db_archive):
        """RT-1: overflow con archive_dir hace archive-and-purge de
        sincronizados, preservando pendientes."""
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
        temp_db_archive.add_records(synced_records + pending_records)

        # Marcar 60 más antiguos como sincronizados
        unsynced = temp_db_archive.get_unsynced_records(limit=1000)
        assert len(unsynced) == 110
        temp_db_archive.mark_as_synced([r["id"] for r in unsynced[:60]])

        # Un registro más dispara overflow (111 > 100): archiva + purga los
        # sincronizados más antiguos, conserva los 51 pendientes
        temp_db_archive.add_records(
            [
                AttendanceRecordDB(
                    user_id="extra", timestamp=datetime.now(),
                    status=0, device_ip="192.168.1.101", punch_type="entrada",
                )
            ]
        )

        stats = temp_db_archive.get_stats()
        # Se archivaron y purgaron 11 sincronizados; los 51 pendientes intactos
        assert stats["total_records"] == 100
        assert stats["pending_sync"] == 51
        assert stats["synced"] == 49

        # Verificar que existe archivo de archivo y bitácora
        archive_log = temp_db_archive.get_archive_log()
        assert len(archive_log) == 1
        assert archive_log[0]["action"] == "archive_synced"
        assert archive_log[0]["records_archived"] == 11

    def test_synced_40_days_not_purged(self, temp_db):
        """MYK-419 AC: registro sync'd de 40 días NO se borra (fin del purge a 30d)."""
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

    def test_mark_sync_failed_never_discards(self, temp_db):
        """RT-1: registros fallidos nunca se descartan ni se marcan como
        sincronizados tras agotar reintentos; permanecen pendientes."""
        records = [
            AttendanceRecordDB(
                user_id="1", timestamp=datetime.now(), status=0,
                device_ip="192.168.1.101", punch_type="entrada",
            )
        ]
        temp_db.add_records(records)
        unsynced = temp_db.get_unsynced_records()
        record_id = unsynced[0]["id"]

        # Marcar como fallido 6 veces (más allá de max_attempts=5)
        for _ in range(6):
            temp_db.mark_sync_failed([record_id], max_attempts=5)

        # Debe seguir sin sincronizar (synced=0), nunca descartado
        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 1
        assert unsynced[0]["id"] == record_id

    def test_archive_synced_older_than_then_purge(self, tmp_path):
        """RT-1: purge solo procede tras archivo exitoso (archive-and-purge).

        1. Crear registros sincronizados antiguos y recientes
        2. Archivar (exportar) los antiguos
        3. Intentar purgar sin archivar -> no borra nada
        4. Purgar tras archivo exitoso -> borra solo los archivados
        """
        repo = BufferRepository(tmp_path / "rt1.db", max_records=10000)
        now = datetime.now()

        repo.add_records([
            AttendanceRecordDB(
                user_id="viejo", timestamp=now - timedelta(days=800),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            ),
            AttendanceRecordDB(
                user_id="reciente", timestamp=now - timedelta(days=100),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            ),
        ])
        unsynced = repo.get_unsynced_records()
        ids = {r["user_id"]: r["id"] for r in unsynced}
        repo.mark_as_synced([ids["viejo"], ids["reciente"]])

        # Sin archivar primero, purge no debe borrar nada
        deleted = repo.purge_synced_older_than(
            days=730, reason="purga sin archivo", operator="dba"
        )
        assert deleted == 0
        assert repo.get_stats()["total_records"] == 2

        # Archivar registros > 730 días
        export_path = tmp_path / "export.csv"
        archived = repo.archive_synced_older_than(
            days=730, export_path=export_path,
            reason="archivo previo a purge", operator="dba"
        )
        assert archived == 1
        assert export_path.exists()

        # Ahora purge solo borra los archivados
        deleted = repo.purge_synced_older_than(
            days=730, reason="purga tras archivo", operator="dba"
        )
        assert deleted == 1
        stats = repo.get_stats()
        assert stats["total_records"] == 1
        assert stats["pending_sync"] == 0  # reciente sigue vivo (no era > 730d)
        # reciente sigue consultable
        with repo.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE user_id = 'reciente'"
            ).fetchone()
        assert row[0] == 1

        # Bitácoras: hay 2 entradas (1 del purge sin archivo que borró 0,
        # 1 del purge tras archivo que borró 1)
        audit = repo.get_retention_audit()
        assert len(audit) == 2
        assert audit[0]["action"] == "purge_synced"
        assert audit[0]["records_deleted"] == 1
        assert audit[0]["operator"] == "dba"

        archlog = repo.get_archive_log()
        assert len(archlog) == 1
        assert archlog[0]["action"] == "archive_synced"

    def test_records_25_months_consultable_with_default(self, temp_db):
        """RT-1 AC: con default (26 meses ~= 790 días), registros de hace
        25 meses (~762 días) siguen consultables."""
        now = datetime.now()
        temp_db.add_records([
            AttendanceRecordDB(
                user_id="veinticinco_meses",
                timestamp=now - timedelta(days=762),  # ~25 meses
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            ),
            AttendanceRecordDB(
                user_id="veintiseis_meses_un_dia",
                timestamp=now - timedelta(days=791),  # > 26 meses
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            ),
        ])

        # Ambos siguen en el buffer (no hay purge automático por antigüedad)
        stats = temp_db.get_stats()
        assert stats["total_records"] == 2

        with temp_db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE user_id = 'veinticinco_meses'"
            ).fetchone()
        assert row[0] == 1

    def test_manual_purge_requires_reason_and_operator(self, temp_db):
        """MYK-419: sin reason/operator no hay borrado manual (bitácora obligatoria)"""
        temp_db.add_records([
            AttendanceRecordDB(
                user_id="x", timestamp=datetime.now() - timedelta(days=999),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            )
        ])
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="", operator="dba")
        with pytest.raises(ValueError):
            temp_db.purge_synced_older_than(days=730, reason="ok", operator="")
        assert temp_db.get_stats()["total_records"] == 1
        assert temp_db.get_retention_audit() == []

    def test_archive_requires_reason_and_operator(self, temp_db):
        """RT-1: archivado requiere reason y operator (bitácora obligatoria)"""
        temp_db.add_records([
            AttendanceRecordDB(
                user_id="x", timestamp=datetime.now() - timedelta(days=999),
                status=0, device_ip="192.168.1.101", punch_type="entrada",
            )
        ])
        temp_db.mark_as_synced([temp_db.get_unsynced_records()[0]["id"]])

        with pytest.raises(ValueError):
            temp_db.archive_synced_older_than(
                days=730, export_path="/tmp/x.csv", reason="", operator="dba"
            )
        with pytest.raises(ValueError):
            temp_db.archive_synced_older_than(
                days=730, export_path="/tmp/x.csv", reason="ok", operator=""
            )

    def test_log_sync(self, temp_db):
        """Test de log de sincronización"""
        temp_db.log_sync(
            records_synced=10, records_failed=0, status="success", duration_seconds=1.5
        )

        history = temp_db.get_sync_history()

        assert len(history) == 1
        assert history[0]["records_synced"] == 10
        assert history[0]["status"] == "success"
