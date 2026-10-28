"""
Repositorio para Buffer Local SQLite
Manejo de registros de asistencia en disco
"""

import contextlib
import csv
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..utils.timezones import coerce_timezone, ensure_aware
from .models import AttendanceRecordDB

logger = logging.getLogger(__name__)

# Retención legal por defecto: 26 meses (~790 días) = último año + 1 año
# tras la baja + margen (LFT 804-III, RT-1 / MYK-428).
DEFAULT_RETENTION_DAYS = 790


class BufferRepository:
    """
    Repositorio para almacenamiento local de registros de asistencia

    Características:
    - Almacenamiento offline
    - Cola de sincronización pendiente
    - Retención legal LFT 804-III: SIN borrado automático por antigüedad;
      el borrado es manual (purge_synced_older_than) con entrada en bitácora
      (tabla retention_audit). Los registros pendientes (synced=0) NUNCA se
      borran ni se descartan por agotar reintentos de sync.
    - Archive-and-purge: el borrado de registros sincronizados requiere
      exportación previa (archivo) y solo aplica a registros archivados.
    - Transacciones atómicas
    - Conexión thread-safe
    """

    def __init__(
        self,
        db_path: Path,
        max_records: int = 10000,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        default_timezone=None,
        archive_dir: Path | None = None,
    ):
        self.db_path = Path(db_path)
        self.max_records = max_records
        self.retention_days = retention_days
        self.archive_dir = Path(archive_dir) if archive_dir is not None else None
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
        if self.archive_dir is not None:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

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
                    last_sync_attempt DATETIME,
                    archived BOOLEAN DEFAULT 0,
                    archived_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Columnas additivas para bases existentes (RT-1 / MYK-428):
            # archived / archived_at marcan registros exportados antes del purge.
            for col_def in ("archived BOOLEAN DEFAULT 0", "archived_at DATETIME"):
                with contextlib.suppress(sqlite3.OperationalError):
                    cursor.execute(
                        f"ALTER TABLE attendance_records ADD COLUMN {col_def}"
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

            # Índice para purge de registros archivados (RT-1)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_archived_timestamp
                ON attendance_records(archived, timestamp)
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

            # Bitácora de retención (MYK-419, LFT 804-III): todo borrado de
            # registros de asistencia es manual y debe quedar registrado aquí.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS retention_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    records_deleted INTEGER NOT NULL,
                    cutoff_date TEXT,
                    reason TEXT,
                    operator TEXT
                )
            """)

            # Bitácora de archivado (RT-1 / MYK-428): registro de exportaciones
            # previas al purge, para permitir purge solo de registros archivados.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS archive_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    records_archived INTEGER NOT NULL,
                    cutoff_date TEXT,
                    export_path TEXT,
                    reason TEXT,
                    operator TEXT
                )
            """)

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

            # Compacción de capacidad: SOLO registros ya sincronizados y
            # archivados. LFT 804-III: nunca se borra por antigüedad ni
            # pendientes. Si no hay archive_dir configurado, NO se borra nada
            # (archive-and-purge requiere export previo).
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
                WHERE synced = 0
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
        Marcar registros como fallidos en sincronización.

        LFT 804-III: los registros fallidos NUNCA se descartan ni se marcan
        como sincronizados por agotar reintentos. Se incrementan los intentos
        y se deja synced = 0 para que sigan siendo consultables y reintentados
        en el siguiente ciclo.
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
                    last_sync_attempt = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """,
                list(record_ids),
            )

            cursor.execute(
                f"""
                SELECT id, sync_attempts FROM attendance_records
                WHERE id IN ({placeholders}) AND sync_attempts >= ?
            """,
                list(record_ids) + [max_attempts],
            )
            exceeded = cursor.fetchall()
            for row in exceeded:
                logger.warning(
                    f"Registro {row['id']} alcanzó {row['sync_attempts']} intentos "
                    f"de sincronización sin éxito: se retiene pendiente "
                    f"(LFT 804-III, no se descarta)"
                )

    def _enforce_capacity(self, conn):
        """
        Compacción del buffer al exceder max_records.

        LFT 804-III: el overflow SOLO compacta registros ya sincronizados
        Y archivados (exportados previamente). Los registros pendientes
        (synced=0) NUNCA se borran.

        Si no hay archive_dir configurado, NO se borra nada: se registra un
        aviso crítico para que el operador configure archive-and-purge o
        libere el buffer restaurando el sync.
        """
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM attendance_records")
        count = cursor.fetchone()[0]

        if count <= self.max_records:
            return

        excess = count - self.max_records

        if self.archive_dir is None:
            cursor.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE synced = 0"
            )
            pending = cursor.fetchone()[0]
            logger.critical(
                f"Buffer sobre capacidad ({count} > max_records={self.max_records}) "
                f"sin archive_dir: NO se borra ningún registro (LFT 804-III). "
                f"Pendientes={pending}. Configurar archive_dir para habilitar "
                f"archive-and-purge."
            )
            return

        # Archive-and-purge: exportar primero los más antiguos sincronizados,
        # luego purgarlos solo si la exportación tuvo éxito.
        archived = self._archive_oldest_synced(conn, excess)
        if archived == 0:
            logger.critical(
                f"Buffer sobre capacidad ({count} > max_records={self.max_records}) "
                f"y no se pudo archivar ningún registro: NO se borra nada "
                f"(LFT 804-III)."
            )
            return

        # Purgar solo los registros archivados que acabamos de exportar
        cursor.execute(
            """
            DELETE FROM attendance_records
            WHERE archived = 1 AND synced = 1
            ORDER BY timestamp ASC
            LIMIT ?
        """,
            (archived,),
        )
        deleted = cursor.rowcount if cursor.rowcount is not None else 0
        if deleted > 0:
            logger.warning(
                f"Capacidad excedida: {archived} registros archivados exportados "
                f"y {deleted} purgados (archive-and-purge, LFT 804-III)"
            )

    def _archive_oldest_synced(self, conn, limit: int) -> int:
        """
        Exporta los `limit` registros sincronizados más antiguos a CSV en
        archive_dir y los marca como archivados. Devuelve el número
        efectivamente archivado.
        """
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, timestamp, status, device_ip, punch_type,
                   synced, sync_attempts, last_sync_attempt, created_at
            FROM attendance_records
            WHERE synced = 1 AND archived = 0
            ORDER BY timestamp ASC, id ASC
            LIMIT ?
        """,
            (limit,),
        )
        rows = cursor.fetchall()
        if not rows:
            return 0

        export_path = self.archive_dir / (
            f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        try:
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "id",
                        "user_id",
                        "timestamp",
                        "status",
                        "device_ip",
                        "punch_type",
                        "synced",
                        "sync_attempts",
                        "last_sync_attempt",
                        "created_at",
                    ]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row["id"],
                            row["user_id"],
                            row["timestamp"],
                            row["status"],
                            row["device_ip"],
                            row["punch_type"],
                            row["synced"],
                            row["sync_attempts"],
                            row["last_sync_attempt"],
                            row["created_at"],
                        ]
                    )
        except OSError as e:
            logger.error(f"No se pudo escribir archivo de archivo {export_path}: {e}")
            return 0

        record_ids = [row["id"] for row in rows]
        placeholders = ",".join("?" * len(record_ids))
        cursor.execute(
            f"""
            UPDATE attendance_records
            SET archived = 1,
                archived_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """,
            record_ids,
        )

        cursor.execute(
            """
            INSERT INTO archive_log
            (action, records_archived, cutoff_date, export_path, reason, operator)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                "archive_synced",
                len(record_ids),
                rows[-1]["timestamp"],
                str(export_path),
                "archive-and-purge por exceder max_records",
                "system",
            ),
        )

        logger.info(
            f"Archivados {len(record_ids)} registros sincronizados en {export_path}"
        )
        return len(record_ids)

    def archive_synced_older_than(
        self, days: int, export_path: Path, reason: str, operator: str
    ) -> int:
        """
        Exporta (archiva) registros sincronizados más antiguos que `days` días
        a un archivo CSV antes de poder purgarlos.

        LFT 804-III (RT-1 / MYK-428): el purge solo procede tras archivo
        exitoso. Este método realiza la exportación y marca los registros como
        archivados para que `purge_synced_older_than` pueda borrarlos.

        Args:
            days: Antigüedad mínima en días para archivar
            export_path: Ruta del archivo CSV de destino
            reason: Motivo del archivado (bitácora obligatoria)
            operator: Operador que ejecuta el archivado (bitácora obligatoria)

        Returns:
            Número de registros archivados
        """
        if not reason or not reason.strip():
            raise ValueError("reason obligatorio: archivado requiere bitácora")
        if not operator or not operator.strip():
            raise ValueError("operator obligatorio: archivado requiere bitácora")
        if days < 0:
            raise ValueError("days no puede ser negativo")

        export_path = Path(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, user_id, timestamp, status, device_ip, punch_type,
                       synced, sync_attempts, last_sync_attempt, created_at
                FROM attendance_records
                WHERE synced = 1 AND archived = 0 AND timestamp < ?
                ORDER BY timestamp ASC, id ASC
            """,
                (cutoff_date,),
            )
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(
                    """
                    INSERT INTO archive_log
                    (action, records_archived, cutoff_date, export_path, reason, operator)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        "archive_synced",
                        0,
                        cutoff_date,
                        str(export_path),
                        reason.strip(),
                        operator.strip(),
                    ),
                )
                return 0

            try:
                with open(export_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "id",
                            "user_id",
                            "timestamp",
                            "status",
                            "device_ip",
                            "punch_type",
                            "synced",
                            "sync_attempts",
                            "last_sync_attempt",
                            "created_at",
                        ]
                    )
                    for row in rows:
                        writer.writerow(
                            [
                                row["id"],
                                row["user_id"],
                                row["timestamp"],
                                row["status"],
                                row["device_ip"],
                                row["punch_type"],
                                row["synced"],
                                row["sync_attempts"],
                                row["last_sync_attempt"],
                                row["created_at"],
                            ]
                        )
            except OSError as e:
                logger.error(f"No se pudo escribir archivo de archivo {export_path}: {e}")
                raise

            record_ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(record_ids))
            cursor.execute(
                f"""
                UPDATE attendance_records
                SET archived = 1,
                    archived_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """,
                record_ids,
            )

            cursor.execute(
                """
                INSERT INTO archive_log
                (action, records_archived, cutoff_date, export_path, reason, operator)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    "archive_synced",
                    len(record_ids),
                    cutoff_date,
                    str(export_path),
                    reason.strip(),
                    operator.strip(),
                ),
            )

            logger.info(
                f"Archivados {len(record_ids)} registros sincronizados en "
                f"{export_path} por {operator}: {reason}"
            )
            return len(record_ids)

    def purge_synced_older_than(self, days: int, reason: str, operator: str) -> int:
        """
        Borrado MANUAL de registros sincronizados Y archivados más antiguos que
        `days` días.

        LFT 804-III (RT-1 / MYK-428): única vía de borrado por antigüedad.
        Solo se borran registros que han sido archivados previamente
        (exportación exitosa). Nunca borra pendientes de sync. Requiere
        `reason` y `operator` no vacíos y deja entrada obligatoria en la
        bitácora (retention_audit).

        Returns:
            Número de registros eliminados
        """
        if not reason or not reason.strip():
            raise ValueError("reason obligatorio: borrado manual requiere bitácora")
        if not operator or not operator.strip():
            raise ValueError("operator obligatorio: borrado manual requiere bitácora")
        if days < 0:
            raise ValueError("days no puede ser negativo")

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM attendance_records
                WHERE synced = 1 AND archived = 1 AND timestamp < ?
            """,
                (cutoff_date,),
            )
            deleted = cursor.rowcount if cursor.rowcount is not None else 0

            cursor.execute(
                """
                INSERT INTO retention_audit
                (action, records_deleted, cutoff_date, reason, operator)
                VALUES ('purge_synced', ?, ?, ?, ?)
            """,
                (deleted, cutoff_date, reason.strip(), operator.strip()),
            )

            if deleted > 0:
                logger.warning(
                    f"Borrado manual: {deleted} registros sincronizados y "
                    f"archivados < {cutoff_date} por {operator}: {reason}"
                )
            return deleted

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

    def get_archive_log(self, limit: int = 50) -> list[dict]:
        """
        Obtener bitácora de archivado (exportaciones previas al purge).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM archive_log
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

            # Pendientes de sync
            cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE synced = 0")
            pending = cursor.fetchone()[0]

            # Sincronizados
            cursor.execute("SELECT COUNT(*) FROM attendance_records WHERE synced = 1")
            synced = cursor.fetchone()[0]

            # Archivado (sync + archived)
            cursor.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE synced = 1 AND archived = 1"
            )
            archived = cursor.fetchone()[0]

            # Más antiguo pendiente
            cursor.execute("""
                SELECT MIN(timestamp) FROM attendance_records WHERE synced = 0
            """)
            oldest_pending = cursor.fetchone()[0]

            # Más reciente
            cursor.execute("SELECT MAX(timestamp) FROM attendance_records")
            newest = cursor.fetchone()[0]

            return {
                "total_records": total,
                "pending_sync": pending,
                "synced": synced,
                "archived": archived,
                "max_records": self.max_records,
                "retention_days": self.retention_days,
                "oldest_pending": oldest_pending,
                "newest_record": newest,
                "usage_percent": (total / self.max_records * 100)
                if self.max_records > 0
                else 0,
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
        (retention_audit) por LFT 804-III (MYK-419).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance_records")
            total = cursor.fetchone()[0]
            cursor.execute("DELETE FROM attendance_records")
            cursor.execute("DELETE FROM sync_log")
            cursor.execute(
                """
                INSERT INTO retention_audit
                (action, records_deleted, reason, operator)
                VALUES ('clear_all', ?, ?, ?)
            """,
                (total, "clear_all(): borrado manual completo del buffer", "unknown"),
            )
            logger.warning("Todos los registros del buffer han sido eliminados")
