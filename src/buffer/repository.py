"""
Repositorio para Buffer Local SQLite
Manejo de registros de asistencia en disco
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..utils.timezones import coerce_timezone, ensure_aware
from .models import AttendanceRecordDB

logger = logging.getLogger(__name__)


class BufferRepository:
    """
    Repositorio para almacenamiento local de registros de asistencia

    Características:
    - Almacenamiento offline (hasta 10,000 registros)
    - Cola de sincronización pendiente
    - Retención legal LFT 804-III (MYK-419/428): SIN borrado automático por
      antigüedad. El overflow ARCHIVA registros ya sincronizados (tabla
      attendance_archive) en lugar de borrarlos; los pendientes y los fallidos
      NUNCA se borran ni archivan. El borrado es manual (opt-in), SOLO tras
      exportación previa verificada (purge_synced_older_than /
      purge_archived_older_than), con entrada en bitácora (retention_audit).
    - Transacciones atómicas
    - Conexión thread-safe
    """

    def __init__(self, db_path: Path, max_records: int = 10000, default_timezone=None):
        self.db_path = Path(db_path)
        self.max_records = max_records
        # Huso usado para localizar timestamps naive del firmware antes de
        # persistir (MYK-420): todo registro queda ISO-8601 con offset.
        self.default_tz = coerce_timezone(default_timezone)
        self._init_database()

    @contextmanager
    def get_connection(self):
        """Context manager para conexiones SQLite"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_database(self):
        """Inicializar base de datos y tablas"""
        # Crear directorio si no existe
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tabla de registros de asistencia
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    status INTEGER NOT NULL,
                    device_ip TEXT NOT NULL,
                    punch_type TEXT,
                    synced BOOLEAN DEFAULT 0,
                    sync_attempts INTEGER DEFAULT 0,
                    sync_failed BOOLEAN DEFAULT 0,
                    last_sync_attempt DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bases existentes (pre-MYK-428): añadir sync_failed en caliente.
            # SQLite no soporta IF NOT EXISTS en ALTER: se tolera el error de
            # columna duplicada.
            with suppress(sqlite3.OperationalError):
                cursor.execute(
                    "ALTER TABLE attendance_records ADD COLUMN sync_failed BOOLEAN DEFAULT 0"
                )

            # Índices para rendimiento
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_synced
                ON attendance_records(synced, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON attendance_records(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id
                ON attendance_records(user_id)
            """)

            # Deduplicar registros existentes (polls repetidos insertaban el
            # mismo log del dispositivo cada vez) y garantizar idempotencia con
            # un índice único. Clave natural: (user_id, timestamp, device_ip).
            cursor.execute("""
                DELETE FROM attendance_records
                WHERE id NOT IN (
                    SELECT MIN(id) FROM attendance_records
                    GROUP BY user_id, timestamp, device_ip
                )
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance
                ON attendance_records(user_id, timestamp, device_ip)
            """)

            # Tabla de log de sincronización
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    records_synced INTEGER,
                    records_failed INTEGER,
                    status TEXT,
                    error_message TEXT,
                    duration_seconds REAL
                )
            """)

            # Archivo de registros (MYK-428, LFT 804-III): el overflow mueve
            # aquí los registros sincronizados en vez de borrarlos. Siguen
            # consultables (get_archived_records) y solo salen por purga
            # manual con exportación previa (purge_archived_older_than).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    status INTEGER NOT NULL,
                    device_ip TEXT NOT NULL,
                    punch_type TEXT,
                    synced BOOLEAN DEFAULT 0,
                    sync_attempts INTEGER DEFAULT 0,
                    sync_failed BOOLEAN DEFAULT 0,
                    last_sync_attempt DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME,
                    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    archive_reason TEXT
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_timestamp
                ON attendance_archive(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_user_id
                ON attendance_archive(user_id)
            """)

            # Bitácora de retención (MYK-419, LFT 804-III): todo borrado de
            # registros de asistencia es manual y debe quedar registrado aquí.
            # MYK-428: export_path evidencia la exportación previa a la purga.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retention_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    records_deleted INTEGER NOT NULL,
                    cutoff_date TEXT,
                    reason TEXT,
                    operator TEXT,
                    export_path TEXT
                )
            """)

            # Bases existentes (pre-MYK-428): añadir export_path en caliente.
            with suppress(sqlite3.OperationalError):
                cursor.execute("ALTER TABLE retention_audit ADD COLUMN export_path TEXT")

            logger.info(f"Base de datos inicializada: {self.db_path}")

    def add_records(self, records: list[AttendanceRecordDB]) -> int:
        """
        Agregar registros al buffer

        Args:
            records: Lista de AttendanceRecordDB

        Returns:
            Número de registros agregados
        """
        if not records:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # INSERT OR IGNORE: el dispositivo devuelve su log completo en cada
            # poll; el índice único (user_id, timestamp, device_ip) descarta los
            # duplicados y hace el polling idempotente.
            cursor.executemany(
                """
                INSERT OR IGNORE INTO attendance_records
                (user_id, timestamp, status, device_ip, punch_type)
                VALUES (?, ?, ?, ?, ?)
            """,
                [
                    (
                        r.user_id,
                        self._serialize_timestamp(r.timestamp),
                        r.status,
                        r.device_ip,
                        r.punch_type,
                    )
                    for r in records
                ],
            )

            inserted = int(cursor.rowcount)

            # Compacción de capacidad: SOLO registros ya sincronizados.
            # LFT 804-III: nunca se borra por antigüedad ni pendientes.
            self._enforce_capacity(conn)

            logger.info(
                f"Agregados {inserted} registros al buffer "
                f"({len(records) - inserted} duplicados ignorados)"
            )
            return inserted

    def _serialize_timestamp(self, timestamp: Any) -> str:
        """
        Serializa a ISO-8601 con offset (MYK-420).

        - datetime aware: conserva el offset del dispositivo.
        - datetime naive (firmware): se localiza con default_timezone.
        - cualquier otro valor: str() tal cual (legacy).
        """
        if isinstance(timestamp, datetime):
            aware = ensure_aware(timestamp, self.default_tz)
            return aware.isoformat()
        if hasattr(timestamp, "isoformat"):
            return str(timestamp.isoformat())
        return str(timestamp)

    def get_unsynced_records(self, limit: int = 1000) -> list[dict]:
        """
        Obtener registros pendientes de sincronizar

        Args:
            limit: Máximo de registros a retornar

        Returns:
            Lista de registros sin sincronizar
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, user_id, timestamp, status, device_ip, punch_type
                FROM attendance_records
                WHERE synced = 0 AND (sync_failed = 0 OR sync_failed IS NULL)
                ORDER BY timestamp ASC, id ASC
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "timestamp": row["timestamp"],
                    "status": row["status"],
                    "device_ip": row["device_ip"],
                    "punch_type": row["punch_type"],
                }
                for row in rows
            ]

    def mark_as_synced(self, record_ids: list[int]) -> int:
        """
        Marcar registros como sincronizados

        Args:
            record_ids: IDs de registros a marcar

        Returns:
            Número de registros actualizados
        """
        if not record_ids:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()

            placeholders = ",".join("?" * len(record_ids))
            cursor.execute(
                f"""
                UPDATE attendance_records
                SET synced = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """,
                record_ids,
            )

            updated = cursor.rowcount
            logger.debug(f"Marcados {updated} registros como sincronizados")
            return updated if updated is not None else 0

    def mark_sync_failed(self, record_ids: list[int], max_attempts: int = 5):
        """
        Registrar intento de sincronización fallido.

        MYK-428 (LFT 804-III): tras agotar `max_attempts` el registro queda
        marcado `sync_failed=1` (NUNCA `synced=1`): permanece en el buffer,
        consultable y a salvo de archivo/purga. Sale de la cola de sync para
        no reintentar en bucle; se revisa con get_failed_records().
        """
        if not record_ids:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()

            placeholders = ",".join("?" * len(record_ids))
            cursor.execute(
                f"""
                UPDATE attendance_records
                SET sync_attempts = sync_attempts + 1,
                    last_sync_attempt = CURRENT_TIMESTAMP,
                    sync_failed = CASE
                        WHEN sync_attempts + 1 >= ? THEN 1
                        ELSE 0
                    END
                WHERE id IN ({placeholders})
            """,
                [max_attempts] + record_ids,
            )

    def get_failed_records(self, limit: int = 1000) -> list[dict]:
        """
        Registros que agotaron sus intentos de sync (sync_failed=1).

        MYK-428: son datos con valor legal; se conservan hasta resolución
        manual (nunca se archivan ni purgan por antigüedad).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, user_id, timestamp, status, device_ip, punch_type,
                       sync_attempts, last_sync_attempt
                FROM attendance_records
                WHERE sync_failed = 1
                ORDER BY last_sync_attempt DESC, id DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def _enforce_capacity(self, conn):
        """
        Archive-and-purge al exceder max_records (MYK-428, LFT 804-III).

        El overflow ARCHIVA los registros ya sincronizados más antiguos
        (INSERT INTO attendance_archive + DELETE, misma transacción) en
        lugar de borrarlos: siguen consultables y solo salen por purga
        manual con exportación previa. Los pendientes (synced=0) y los
        fallidos (sync_failed=1) NUNCA se tocan.
        """
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM attendance_records")
        count = cursor.fetchone()[0]

        if count <= self.max_records:
            return

        excess = count - self.max_records
        cursor.execute(
            """
            INSERT INTO attendance_archive
                (source_id, user_id, timestamp, status, device_ip, punch_type,
                 synced, sync_attempts, sync_failed, last_sync_attempt,
                 created_at, updated_at, archive_reason)
            SELECT id, user_id, timestamp, status, device_ip, punch_type,
                   synced, sync_attempts, sync_failed, last_sync_attempt,
                   created_at, updated_at, 'capacity_overflow'
            FROM attendance_records
            WHERE synced = 1 AND (sync_failed = 0 OR sync_failed IS NULL)
            ORDER BY timestamp ASC
            LIMIT ?
        """,
            (excess,),
        )
        archived = cursor.rowcount if cursor.rowcount is not None else 0

        cursor.execute(
            """
            DELETE FROM attendance_records
            WHERE id IN (
                SELECT id FROM attendance_records
                WHERE synced = 1 AND (sync_failed = 0 OR sync_failed IS NULL)
                ORDER BY timestamp ASC
                LIMIT ?
            )
        """,
            (excess,),
        )

        if archived > 0:
            cursor.execute(
                """
                INSERT INTO retention_audit
                    (action, records_deleted, reason, operator)
                VALUES ('archive_overflow', 0, ?, 'system')
            """,
                (
                    f"Capacidad excedida: {archived} registros sincronizados "
                    f"archivados en attendance_archive (max_records="
                    f"{self.max_records})",
                ),
            )
            logger.info(
                f"Capacidad excedida: {archived} registros sincronizados "
                f"archivados (no borrados) en attendance_archive"
            )

        cursor.execute(
            """
            SELECT COUNT(*) FROM attendance_records
            WHERE synced = 0 AND (sync_failed = 0 OR sync_failed IS NULL)
        """
        )
        pending = cursor.fetchone()[0]
        if pending > self.max_records:
            logger.critical(
                f"Buffer sobre capacidad con {pending} registros PENDIENTES de sync "
                f"(max_records={self.max_records}). Nada se borra (LFT 804-III): "
                f"restaurar el sync para drenar el buffer."
            )

    @staticmethod
    def _export_records_to_json(records: list[dict], export_path: str, cutoff_date: str) -> int:
        """
        Exportar registros a JSON y VERIFICAR la escritura (MYK-428).

        La exportación exitosa es precondición de toda purga (LFT 804-III:
        archive-and-purge). Escribe, fsync y relee para verificar que el
        archivo contiene exactamente los registros a purgar; cualquier
        fallo levanta RuntimeError ANTES de que la purga borre algo.
        """
        if not export_path or not str(export_path).strip():
            raise ValueError("export_path obligatorio: la purga requiere exportación previa")

        path = Path(str(export_path).strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "exported_at": datetime.now().isoformat(),
            "cutoff_date": cutoff_date,
            "count": len(records),
            "records": records,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())

        with open(path, encoding="utf-8") as f:
            verify = json.load(f)
        if verify.get("count") != len(records) or len(verify.get("records", [])) != len(records):
            raise RuntimeError(
                f"Exportación verificada fallida en {path}: se esperaban {len(records)} registros"
            )
        return len(records)

    def purge_synced_older_than(
        self, days: int, reason: str, operator: str, export_path: str | None = None
    ) -> int:
        """
        Borrado MANUAL (opt-in) de registros sincronizados más antiguos que
        `days` días. MYK-428 (LFT 804-III): requiere exportación previa
        verificada (`export_path`); si la exportación falla NO se borra nada.
        Nunca borra pendientes ni fallidos. Requiere `reason` y `operator`
        no vacíos y deja entrada obligatoria en la bitácora (retention_audit).

        Returns:
            Número de registros eliminados
        """
        if not reason or not reason.strip():
            raise ValueError("reason obligatorio: borrado manual requiere bitácora")
        if not operator or not operator.strip():
            raise ValueError("operator obligatorio: borrado manual requiere bitácora")
        if days < 0:
            raise ValueError("days no puede ser negativo")
        if not export_path or not str(export_path).strip():
            raise ValueError(
                "export_path obligatorio: la purga requiere exportación previa (MYK-428)"
            )

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Exportación previa OBLIGATORIA: falla -> excepción -> nada borrado
            cursor.execute(
                """
                SELECT * FROM attendance_records
                WHERE synced = 1 AND (sync_failed = 0 OR sync_failed IS NULL)
                  AND timestamp < ?
                ORDER BY timestamp ASC
            """,
                (cutoff_date,),
            )
            to_purge = [dict(row) for row in cursor.fetchall()]
            self._export_records_to_json(to_purge, export_path, cutoff_date)

            cursor.execute(
                """
                DELETE FROM attendance_records
                WHERE synced = 1 AND (sync_failed = 0 OR sync_failed IS NULL)
                  AND timestamp < ?
            """,
                (cutoff_date,),
            )
            deleted = cursor.rowcount if cursor.rowcount is not None else 0

            cursor.execute(
                """
                INSERT INTO retention_audit
                (action, records_deleted, cutoff_date, reason, operator, export_path)
                VALUES ('purge_synced', ?, ?, ?, ?, ?)
            """,
                (deleted, cutoff_date, reason.strip(), operator.strip(), str(export_path)),
            )

            if deleted > 0:
                logger.warning(
                    f"Borrado manual: {deleted} registros sincronizados < {cutoff_date} "
                    f"por {operator}: {reason} (export: {export_path})"
                )
            return deleted

    def purge_archived_older_than(
        self, days: int, reason: str, operator: str, export_path: str | None = None
    ) -> int:
        """
        Borrado MANUAL (opt-in) SOLO de registros ARCHIVADOS más antiguos que
        `days` días. MYK-428 (LFT 804-III): es la única purga conformante del
        flujo archive-and-purge (overflow archiva -> esta purga elimina tras
        exportación previa verificada). Si la exportación falla NO se borra
        nada. Requiere `reason`/`operator` y deja bitácora (retention_audit).

        Returns:
            Número de registros eliminados del archivo
        """
        if not reason or not reason.strip():
            raise ValueError("reason obligatorio: borrado manual requiere bitácora")
        if not operator or not operator.strip():
            raise ValueError("operator obligatorio: borrado manual requiere bitácora")
        if days < 0:
            raise ValueError("days no puede ser negativo")
        if not export_path or not str(export_path).strip():
            raise ValueError(
                "export_path obligatorio: la purga requiere exportación previa (MYK-428)"
            )

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Exportación previa OBLIGATORIA: falla -> excepción -> nada borrado
            cursor.execute(
                """
                SELECT * FROM attendance_archive
                WHERE timestamp < ?
                ORDER BY timestamp ASC
            """,
                (cutoff_date,),
            )
            to_purge = [dict(row) for row in cursor.fetchall()]
            self._export_records_to_json(to_purge, export_path, cutoff_date)

            cursor.execute(
                """
                DELETE FROM attendance_archive
                WHERE timestamp < ?
            """,
                (cutoff_date,),
            )
            deleted = cursor.rowcount if cursor.rowcount is not None else 0

            cursor.execute(
                """
                INSERT INTO retention_audit
                (action, records_deleted, cutoff_date, reason, operator, export_path)
                VALUES ('purge_archived', ?, ?, ?, ?, ?)
            """,
                (deleted, cutoff_date, reason.strip(), operator.strip(), str(export_path)),
            )

            if deleted > 0:
                logger.warning(
                    f"Borrado manual: {deleted} registros archivados < {cutoff_date} "
                    f"por {operator}: {reason} (export: {export_path})"
                )
            return deleted

    def get_archived_records(self, limit: int = 1000, user_id: str | None = None) -> list[dict]:
        """
        Registros archivados (attendance_archive), consultables para
        cumplimiento (LFT 804-III: el archivado no es borrado).
        """
        query = "SELECT * FROM attendance_archive"
        params: list[Any] = []
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_retention_audit(self, limit: int = 50) -> list[dict]:
        """
        Obtener bitácora de retención (borrados manuales).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM retention_audit
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict[str, Any]:
        """
        Obtener estadísticas del buffer

        Returns:
            Dict con estadísticas
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total registros
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            total = cursor.fetchone()[0]

            # Pendientes de sync (excluye fallidos: no se reintentan)
            cursor.execute(
                """
                SELECT COUNT(*) FROM attendance_records
                WHERE synced = 0 AND (sync_failed = 0 OR sync_failed IS NULL)
            """
            )
            pending = cursor.fetchone()[0]

            # Fallidos (agotaron intentos): se conservan, no se reintentan
            cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE sync_failed = 1")
            failed = cursor.fetchone()[0]

            # Sincronizados de verdad (backup en plataforma)
            cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE synced = 1")
            synced = cursor.fetchone()[0]

            # Archivados (overflow): consultables, salen solo por purga manual
            cursor.execute("SELECT COUNT(*) FROM attendance_archive")
            archived = cursor.fetchone()[0]

            # Más antiguo pendiente
            cursor.execute("""
                SELECT MIN(timestamp) FROM attendance_records
                WHERE synced = 0 AND (sync_failed = 0 OR sync_failed IS NULL)
            """)
            oldest_pending = cursor.fetchone()[0]

            # Más reciente
            cursor.execute("SELECT MAX(timestamp) FROM attendance_records")
            newest = cursor.fetchone()[0]

            return {
                "total_records": total,
                "pending_sync": pending,
                "synced": synced,
                "failed_sync": failed,
                "archived_records": archived,
                "oldest_pending": oldest_pending,
                "newest_record": newest,
                "max_records": self.max_records,
                "usage_percent": (total / self.max_records * 100) if self.max_records > 0 else 0,
            }

    def log_sync(
        self,
        records_synced: int,
        records_failed: int,
        status: str,
        error_message: str | None = None,
        duration_seconds: float = 0,
    ):
        """
        Log de operación de sincronización
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO sync_log
                (records_synced, records_failed, status, error_message, duration_seconds)
                VALUES (?, ?, ?, ?, ?)
            """,
                (records_synced, records_failed, status, error_message, duration_seconds),
            )

    def get_sync_history(self, limit: int = 50) -> list[dict]:
        """
        Obtener historial de sincronización
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM sync_log
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def clear_all(self):
        """Limpiar todos los registros (usar con precaución).

        Borrado manual destructivo: queda registrado en la bitácora
        (retention_audit) por LFT 804-III (MYK-419). MYK-428: incluye el
        archivo (attendance_archive) — también son registros de asistencia.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM attendance_archive")
            archived = cursor.fetchone()[0]
            cursor.execute("DELETE FROM attendance_records")
            cursor.execute("DELETE FROM attendance_archive")
            cursor.execute("DELETE FROM sync_log")
            cursor.execute(
                """
                INSERT INTO retention_audit
                (action, records_deleted, reason, operator)
                VALUES ('clear_all', ?, ?, ?)
            """,
                (
                    total + archived,
                    f"clear_all(): borrado manual completo del buffer "
                    f"({archived} venían del archivo attendance_archive)",
                    "unknown",
                ),
            )
            logger.warning("Todos los registros del buffer han sido eliminados")
