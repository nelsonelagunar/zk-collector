"""
Repositorio para Buffer Local SQLite
Manejo de registros de asistencia en disco
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..utils.timezones import coerce_timezone, ensure_aware
from .integrity import ATTESTED_FIELDS, GENESIS_HASH, compute_hash, verify_chain
from .models import AttendanceRecordDB

logger = logging.getLogger(__name__)

# Bitacora append-only + triggers (MYK-422). Mismo DDL que
# migrations/buffer/010_attendance_integrity.sql: el baseline lo aplica a DBs
# nuevas (incluidas instancias sin migrations/ en el layout, ej. pip install);
# la migracion lo aplica a DBs pre-existentes. Todo es IF NOT EXISTS: aplicar
# ambos es idempotente. Mantener sincronizado con el archivo de migracion.
_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS attendance_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER,
    action TEXT NOT NULL
        CHECK (action IN ('update', 'delete', 'annul', 'correction', 'chain_backfill')),
    actor TEXT NOT NULL,
    reason TEXT,
    before_values TEXT,
    after_values TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON attendance_audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON attendance_audit_log(created_at);

CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_update
AFTER UPDATE ON attendance_records
FOR EACH ROW
WHEN OLD.user_id IS NOT NEW.user_id
  OR OLD.timestamp IS NOT NEW.timestamp
  OR OLD.status IS NOT NEW.status
  OR OLD.device_ip IS NOT NEW.device_ip
  OR OLD.punch_type IS NOT NEW.punch_type
BEGIN
    INSERT INTO attendance_audit_log
        (record_id, action, actor, reason, before_values, after_values)
    VALUES
        (OLD.id, 'update', 'trigger',
         'UPDATE directo: campos atestiguados modificados fuera del flujo de correccion',
         json_object('user_id', OLD.user_id, 'timestamp', OLD.timestamp,
                     'status', OLD.status, 'device_ip', OLD.device_ip,
                     'punch_type', OLD.punch_type),
         json_object('user_id', NEW.user_id, 'timestamp', NEW.timestamp,
                     'status', NEW.status, 'device_ip', NEW.device_ip,
                     'punch_type', NEW.punch_type));
END;

CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_delete
AFTER DELETE ON attendance_records
FOR EACH ROW
BEGIN
    INSERT INTO attendance_audit_log
        (record_id, action, actor, reason, before_values)
    VALUES
        (OLD.id, 'delete', 'trigger', 'registro eliminado',
         json_object('user_id', OLD.user_id, 'timestamp', OLD.timestamp,
                     'status', OLD.status, 'device_ip', OLD.device_ip,
                     'punch_type', OLD.punch_type));
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update
BEFORE UPDATE ON attendance_audit_log
BEGIN
    SELECT RAISE(ABORT, 'attendance_audit_log es append-only (MYK-422)');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete
BEFORE DELETE ON attendance_audit_log
BEGIN
    SELECT RAISE(ABORT, 'attendance_audit_log es append-only (MYK-422)');
END;
"""


class BufferRepository:
    """
    Repositorio para almacenamiento local de registros de asistencia

    Características:
    - Almacenamiento offline (hasta 10,000 registros)
    - Cola de sincronización pendiente
    - Retención legal LFT 804-III: SIN borrado automático por antigüedad;
      el borrado es manual (purge_synced_older_than) con entrada en bitácora
      (tabla retention_audit). El overflow solo compacta registros ya
      sincronizados: los pendientes NUNCA se borran.
    - Transacciones atómicas
    - Conexión thread-safe
    - Cadena de integridad SHA-256 (MYK-422): sellado por registro al insertar,
      verificacion via verify_integrity(), correcciones auditadas que no rompen
      la cadena (annul + insert corrected + bitacora).
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

            # Tabla de registros de asistencia. Las columnas de integridad
            # (MYK-422) van en el baseline para DBs nuevas; las DBs pre-existentes
            # las reciben por migrations/buffer/010 (ALTER). El runner de migraciones
            # es tolerante a columnas ya presentes (idempotente).
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
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    record_hash TEXT,
                    prev_hash TEXT,
                    annulled BOOLEAN NOT NULL DEFAULT 0,
                    corrects_record_id INTEGER
                )
            """)

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

            # Unicidad SOLO entre registros activos (migration buffer/010, MYK-422):
            # una correccion con la misma clave natural no colisiona con su
            # original anulado.
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance
                ON attendance_records(user_id, timestamp, device_ip)
                WHERE annulled = 0
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

            # Bitacora append-only + triggers de auditoria (MYK-422): en el
            # baseline para DBs nuevas; migrations/buffer/010 la anade a las
            # pre-existentes. Idempotente en ambos casos.
            for statement in self._split_statements(_AUDIT_DDL):
                cursor.execute(statement)

            # Migraciones versionadas de buffer.db (forward-only). Deben correr
            # ANTES del dedup para que los DELETE sobre datos pre-existentes
            # queden capturados por los triggers de bitacora (MYK-422).
            self._run_buffer_migrations(cursor)

            # Deduplicar registros existentes (polls repetidos insertaban el
            # mismo log del dispositivo cada vez) y garantizar idempotencia con
            # un índice único. Clave natural: (user_id, timestamp, device_ip).
            # Solo entre activos: no debe borrar la fila corregida que comparte
            # clave con su original anulado (MIN(id) seria el anulado).
            cursor.execute("""
                DELETE FROM attendance_records
                WHERE annulled = 0 AND id NOT IN (
                    SELECT MIN(id) FROM attendance_records
                    WHERE annulled = 0
                    GROUP BY user_id, timestamp, device_ip
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

            logger.info(f"Base de datos inicializada: {self.db_path}")

    def _run_buffer_migrations(self, cursor) -> None:
        """
        Aplica migraciones versionadas de buffer.db desde migrations/buffer/*.sql

        Namespace separado del de webgui.db (Database._run_migrations):
        attendance_records vive en buffer.db. Forward-only; el rollback va
        documentado en cada archivo .sql. Numeracion alineada al plan MYK-410.
        """
        migrations_dir = self.db_path.parent.parent / "migrations" / "buffer"

        if not migrations_dir.exists():
            logger.debug("Directorio de migraciones de buffer no encontrado: %s", migrations_dir)
            return

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _buffer_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        applied = {row["name"] for row in cursor.execute("SELECT name FROM _buffer_migrations")}

        for migration_file in sorted(migrations_dir.glob("*.sql")):
            if migration_file.name in applied:
                continue

            logger.info(f"Aplicando buffer migration: {migration_file.name}")
            # Ejecucion por sentencia (no executescript): mantiene la transaccion
            # abierta (atomicidad con el backfill y el registro de _buffer_migrations)
            # y tolera ALTERs ya aplicados en DBs nuevas cuyo baseline ya trae las
            # columnas. El resto del script es idempotente (IF NOT EXISTS).
            for statement in self._split_statements(migration_file.read_text()):
                try:
                    cursor.execute(statement)
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
                    logger.debug("columna ya presente, se omite el ALTER")

            if migration_file.name.startswith("010"):
                sealed = self._backfill_hash_chain(cursor)
                logger.info(f"Backfill de cadena: {sealed} registros sellados")

            cursor.execute(
                "INSERT INTO _buffer_migrations (name) VALUES (?)", (migration_file.name,)
            )

    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """
        Divide un script SQL en sentencias completas.

        sqlite3.complete_statement entiende los bloques BEGIN...END de los
        triggers (no corta en los ';' internos). Comentarios `--` al final de
        un archivo no producen sentancias vacias.
        """
        statements: list[str] = []
        buffer = ""
        for line in sql.splitlines(keepends=True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                statements.append(buffer)
                buffer = ""
        if buffer.strip():
            statements.append(buffer)
        return statements

    def _backfill_hash_chain(self, cursor) -> int:
        """
        Sella (record_hash/prev_hash) los registros pre-migration 010.

        Recorre TODAS las filas por id para mantener continuidad con filas ya
        selladas. Los UPDATE tocan solo columnas no atestiguadas: no generan
        ruido en la bitacora. Devuelve el numero de registros sellados.
        """
        rows = cursor.execute(
            "SELECT id, user_id, timestamp, status, device_ip, punch_type, record_hash "
            "FROM attendance_records ORDER BY id ASC"
        ).fetchall()

        prev = GENESIS_HASH
        sealed = 0
        for row in rows:
            record = dict(row)
            if record["record_hash"] is None:
                record_hash = compute_hash(prev, record)
                cursor.execute(
                    "UPDATE attendance_records SET record_hash = ?, prev_hash = ? WHERE id = ?",
                    (record_hash, prev, record["id"]),
                )
                sealed += 1
                prev = record_hash
            else:
                prev = record["record_hash"]

        if sealed:
            cursor.execute(
                """
                INSERT INTO attendance_audit_log (record_id, action, actor, reason)
                VALUES (NULL, 'chain_backfill', 'system', ?)
                """,
                (f"migration 010: {sealed} registros pre-existentes sellados en la cadena",),
            )
        return sealed

    def _chain_head(self, cursor) -> str:
        """Hash del ultimo registro de la cadena (por id); GENESIS si no hay filas selladas."""
        row = cursor.execute(
            "SELECT record_hash FROM attendance_records ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None or row["record_hash"] is None:
            return GENESIS_HASH
        return str(row["record_hash"])

    def _reseal_chain(self, cursor) -> None:
        """
        Recomputa prev_hash y record_hash de todos los registros restantes
        empezando por GENESIS_HASH. Se usa despues de una purga para que la
        cadena quede continua sin huecos de registros eliminados.
        Los UPDATE tocan solo columnas no atestiguadas (record_hash/prev_hash),
        no generan ruido en la bitacora.
        """
        rows = cursor.execute(
            "SELECT id, user_id, timestamp, status, device_ip, punch_type "
            "FROM attendance_records ORDER BY id ASC"
        ).fetchall()

        prev = GENESIS_HASH
        for row in rows:
            record = dict(row)
            record_hash = compute_hash(prev, record)
            cursor.execute(
                "UPDATE attendance_records SET record_hash = ?, prev_hash = ? WHERE id = ?",
                (record_hash, prev, record["id"]),
            )
            prev = record_hash

    def add_records(self, records: list[AttendanceRecordDB]) -> int:
        """
        Agregar registros al buffer, sellando cada insert en la cadena
        SHA-256 (MYK-422): record_hash = SHA-256(prev_hash || payload).

        El dedup ya no depende solo del indice unico: el NOT EXISTS cubre
        tambien los registros ANULADOS por correccion, evitando que un re-poll
        del mismo log del dispositivo resucite una marcada anulada.

        Args:
            records: Lista de AttendanceRecordDB

        Returns:
            Número de registros agregados
        """
        if not records:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            prev_hash = self._chain_head(cursor)
            inserted = 0

            for r in records:
                # MYK-420: datetime naive del firmware se localiza con el huso
                # por defecto (America/Mexico_City) antes de persistir.
                ts = self._serialize_timestamp(r.timestamp)
                # Coercion de tipos: user_id a str para que el hash sea estable
                # independientemente de si el caller pasa int o str (MYK-442).
                user_id = r.user_id
                if isinstance(user_id, int):
                    user_id = str(user_id)
                values = {
                    "user_id": user_id,
                    "timestamp": ts,
                    "status": r.status,
                    "device_ip": r.device_ip,
                    "punch_type": r.punch_type,
                }
                record_hash = compute_hash(prev_hash, values)
                cursor.execute(
                    """
                    INSERT INTO attendance_records
                        (user_id, timestamp, status, device_ip, punch_type,
                         record_hash, prev_hash)
                    SELECT ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM attendance_records
                        WHERE user_id = ? AND timestamp = ? AND device_ip = ?
                    )
                """,
                    (
                        values["user_id"],
                        values["timestamp"],
                        values["status"],
                        values["device_ip"],
                        values["punch_type"],
                        record_hash,
                        prev_hash,
                        values["user_id"],
                        values["timestamp"],
                        values["device_ip"],
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                    prev_hash = record_hash

            # Limpieza de registros antiguos (edad > 30 dias, sincronizados) y
            # compaccion de capacidad. Ambos dejan huella en attendance_audit_log
            # con actor='purge' para que verify_integrity clasifique los huecos.
            self._purge_old_and_compact(cursor)

            logger.info(
                f"Agregados {inserted} registros al buffer "
                f"({len(records) - inserted} duplicados ignorados)"
            )
            return inserted

    def _purge_old_and_compact(self, cursor) -> int:
        """
        Compacta por capacidad cuando el buffer excede max_records.

        Reglas (MYK-419):
        - Solo se eliminan registros YA SINCRONIZADOS, de los mas antiguos
          primero. Los pendientes de sincronizar NUNCA se borran, aunque el
          buffer exceda temporalmente max_records (se perderia asistencia).
        - No hay purga automatica por antiguedad: la retencion legal
          (LFT 804-III, 2 anos) se aplica solo via purge_synced_older_than()
          con bitacora y operador responsable.

        Despues de eliminar, re-sella la cadena SHA-256 para que los registros
        restantes mantengan prev_hash continuo (el primero cuelga de GENESIS).

        Devuelve el total de registros eliminados.
        """
        deleted = 0
        purged_ids: list[int] = []

        cursor.execute("SELECT COUNT(*) FROM attendance_records")
        count = cursor.fetchone()[0]
        if count > self.max_records:
            excess = count - self.max_records
            cursor.execute(
                """
                SELECT id FROM attendance_records
                WHERE synced = 1
                ORDER BY timestamp ASC, id ASC
                LIMIT ?
                """,
                (excess,),
            )
            purged_ids = [row["id"] for row in cursor.fetchall()]
            if purged_ids:
                placeholders = ",".join("?" * len(purged_ids))
                cursor.execute(
                    f"DELETE FROM attendance_records WHERE id IN ({placeholders})",
                    purged_ids,
                )
                deleted = len(purged_ids)

        # Re-sellar la cadena: recomputar prev_hash/record_hash de todos los
        # registros restantes empezando por GENESIS_HASH.
        if purged_ids:
            self._reseal_chain(cursor)

        if deleted > 0:
            # Registrar cada ID purgado en attendance_audit_log con actor='purge'
            # para que verify_integrity pueda clasificar los huecos.
            for rid in purged_ids:
                cursor.execute(
                    """
                    INSERT INTO attendance_audit_log (record_id, action, actor, reason)
                    VALUES (?, 'delete', 'purge', ?)
                    """,
                    (rid, f"purge_synced_older_than / capacidad: registro {rid} eliminado"),
                )
            logger.info(f"Limpieza completada: {deleted} registros eliminados")

        return deleted

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
                WHERE synced = 0 AND annulled = 0
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
        Marcar registros como fallidos en sincronización

        Args:
            record_ids: IDs de registros
            max_attempts: Máximo de intentos antes de descartar
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
                    synced = CASE
                        WHEN sync_attempts + 1 >= ? THEN 1
                        ELSE 0
                    END
                WHERE id IN ({placeholders})
            """,
                [max_attempts] + record_ids,
            )

    def purge_synced_older_than(self, days: int, reason: str, operator: str) -> int:
        """
        Borrado MANUAL de registros sincronizados más antiguos que `days` días.

        LFT 804-III (MYK-419): única vía de borrado por antigüedad. Nunca
        borra pendientes de sync. Requiere `reason` y `operator` no vacíos y
        deja entrada obligatoria en la bitácora (retention_audit).

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
                WHERE synced = 1 AND timestamp < ?
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

            # Registrar en attendance_audit_log para clasificacion de huecos
            if deleted > 0:
                cursor.execute(
                    """
                    INSERT INTO attendance_audit_log (record_id, action, actor, reason)
                    VALUES (NULL, 'delete', 'purge', ?)
                    """,
                    (f"purge_synced_older_than: {deleted} records < {cutoff_date}",),
                )

            if deleted > 0:
                logger.warning(
                    f"Borrado manual: {deleted} registros sincronizados < {cutoff_date} "
                    f"por {operator}: {reason}"
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

            # Pendientes de sync (los anulados por correccion no se envian, MYK-422)
            cursor.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE synced = 0 AND annulled = 0"
            )
            pending = cursor.fetchone()[0]

            # Más antiguo pendiente
            cursor.execute("""
                SELECT MIN(timestamp) FROM attendance_records
                WHERE synced = 0 AND annulled = 0
            """)
            oldest_pending = cursor.fetchone()[0]

            # Más reciente
            cursor.execute("SELECT MAX(timestamp) FROM attendance_records")
            newest = cursor.fetchone()[0]

            return {
                "total_records": total,
                "pending_sync": pending,
                "synced": total - pending,
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

    def verify_integrity(self) -> dict[str, Any]:
        """
        Verifica la cadena de hashes de attendance_records y resume la bitacora.

        Reporte: valid, algorithm, records_checked, failure_count, failures,
        first_failure, audit_entries, recent_audit, annulled_records,
        purged_records, recorded_purge_gaps.
        Un UPDATE directo de un campo atestiguado produce hash_mismatch; un
        DELETE produce prev_hash_mismatch en la fila siguiente.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            rows = [
                dict(row)
                for row in cursor.execute(
                    """
                    SELECT id, user_id, timestamp, status, device_ip, punch_type,
                           record_hash, prev_hash
                    FROM attendance_records ORDER BY id ASC
                    """
                ).fetchall()
            ]
            report = verify_chain(rows)

            # Add audit summary
            report["audit_entries"] = cursor.execute(
                "SELECT COUNT(*) FROM attendance_audit_log"
            ).fetchone()[0]
            report["recent_audit"] = [
                dict(row)
                for row in cursor.execute(
                    """
                    SELECT id, record_id, action, actor, reason, created_at
                    FROM attendance_audit_log ORDER BY id DESC LIMIT 10
                    """
                ).fetchall()
            ]
            report["annulled_records"] = cursor.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE annulled = 1"
            ).fetchone()[0]

            # Purge gap classification (MYK-442): detectar huecos registrados en bitacora
            # vs eliminaciones no registradas (posible alteracion).
            # Cuando se purga un registro (id=N), el siguiente registro (id=N+1)
            # queda con prev_hash apuntando al hash del purgado, generando
            # prev_hash_mismatch. Si existe una entrada de purge con record_id=N
            # y el registro N+1 sigue presente, se clasifica como recorded_purge_gap.
            # Si N+1 tambien fue eliminado, el hueco ya no es visible.
            report["purged_records"] = 0
            report["recorded_purge_gaps"] = []
            purge_entries = cursor.execute(
                "SELECT record_id FROM attendance_audit_log "
                "WHERE actor = 'purge' AND record_id IS NOT NULL"
            ).fetchall()
            purge_record_ids = {row["record_id"] for row in purge_entries}
            # Solo contar como hueco visible si el registro siguiente existe
            visible_gap_ids = set()
            for row in purge_entries:
                rid = row["record_id"]
                exists = cursor.execute(
                    "SELECT 1 FROM attendance_records WHERE id = ?", (rid + 1,)
                ).fetchone()
                if exists:
                    visible_gap_ids.add(rid)
                    report["purged_records"] += 1
                    report["recorded_purge_gaps"].append({
                        "id": rid + 1,
                        "reason": "recorded_purge_gap",
                        "detail": "hueco por purga registrada en bitacora (actor='purge')",
                        "gap_from": rid,
                        "gap_to": rid,
                    })
            # Filtrar fallos que son huecos de purga registrados (en caso de no re-seal)
            if "failures" in report:
                filtered_failures = []
                for failure in report["failures"]:
                    gap_from = failure.get("id", 0) - 1
                    if gap_from in purge_record_ids:
                        continue  # Excluir este fallo: es un hueco intencional de purga registrada
                    filtered_failures.append(failure)
                report["failures"] = filtered_failures
                report["failure_count"] = len(filtered_failures)
                report["valid"] = len(filtered_failures) == 0
                report["first_failure"] = filtered_failures[0] if filtered_failures else None
            return report

    def correct_record(
        self,
        record_id: int,
        *,
        actor: str,
        reason: str,
        timestamp: str | None = None,
        status: int | None = None,
        punch_type: str | None = None,
        device_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Correccion auditada de una marcada (MYK-422): NUNCA muta el contenido
        atestiguado del original.

        Flujo (una sola transaccion):
          1. Anula el original (annulled=1; fuera del hash -> la cadena queda
             intacta y el contenido queda preservado).
          2. Inserta la fila corregida y la sella en la cadena.
          3. Deja en attendance_audit_log el par annul+correction con
             quien/motivo/valores anterior-posterior.

        Raises:
            ValueError: motivo ausente, sin cambios, o registro ya anulado.
            KeyError: registro inexistente.
            sqlite3.IntegrityError: la correccion colisiona con otro registro
                activo (misma clave natural user_id+timestamp+device_ip).
        """
        if not reason or not reason.strip():
            raise ValueError("El motivo de la correccion es obligatorio")
        if all(v is None for v in (timestamp, status, punch_type, device_ip)):
            raise ValueError("Correccion sin cambios: indica al menos un campo")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                """
                SELECT id, user_id, timestamp, status, device_ip, punch_type, annulled
                FROM attendance_records WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Registro {record_id} no existe")
            original = dict(row)
            if original["annulled"]:
                raise ValueError(f"Registro {record_id} ya esta anulado")

            corrected = {
                "user_id": original["user_id"],
                "timestamp": timestamp if timestamp is not None else original["timestamp"],
                "status": status if status is not None else original["status"],
                "device_ip": device_ip if device_ip is not None else original["device_ip"],
                "punch_type": punch_type if punch_type is not None else original["punch_type"],
            }
            before_values = json.dumps(
                {name: original[name] for name in ATTESTED_FIELDS},
                sort_keys=True,
                ensure_ascii=False,
            )
            after_values = json.dumps(corrected, sort_keys=True, ensure_ascii=False)

            # 1) Anular original (columnas no atestiguadas: sin trigger ni romper cadena)
            cursor.execute(
                """
                UPDATE attendance_records
                SET annulled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (record_id,),
            )

            # 2) Insertar corregido sellado en la cadena
            prev_hash = self._chain_head(cursor)
            record_hash = compute_hash(prev_hash, corrected)
            cursor.execute(
                """
                INSERT INTO attendance_records
                    (user_id, timestamp, status, device_ip, punch_type,
                     record_hash, prev_hash, corrects_record_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    corrected["user_id"],
                    corrected["timestamp"],
                    corrected["status"],
                    corrected["device_ip"],
                    corrected["punch_type"],
                    record_hash,
                    prev_hash,
                    record_id,
                ),
            )
            corrected_id = cursor.lastrowid

            # 3) Bitacora append-only: annul del original + correction de la nueva
            cursor.execute(
                """
                INSERT INTO attendance_audit_log
                    (record_id, action, actor, reason, before_values, after_values)
                VALUES (?, 'annul', ?, ?, ?, ?)
                """,
                (
                    record_id,
                    actor,
                    reason,
                    before_values,
                    json.dumps(
                        {name: original[name] for name in ATTESTED_FIELDS} | {"annulled": True},
                        sort_keys=True,
                        ensure_ascii=False,
                    ),
                ),
            )
            cursor.execute(
                """
                INSERT INTO attendance_audit_log
                    (record_id, action, actor, reason, before_values, after_values)
                VALUES (?, 'correction', ?, ?, ?, ?)
                """,
                (corrected_id, actor, reason, before_values, after_values),
            )

            return {
                "original_id": record_id,
                "corrected_id": corrected_id,
                "record_hash": record_hash,
            }

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
