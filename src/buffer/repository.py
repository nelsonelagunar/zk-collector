"""
Repositorio para Buffer Local SQLite
Manejo de registros de asistencia en disco
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import AttendanceRecordDB

logger = logging.getLogger(__name__)


class BufferRepository:
    """
    Repositorio para almacenamiento local de registros de asistencia

    Características:
    - Almacenamiento offline (hasta 10,000 registros)
    - Cola de sincronización pendiente
    - Limpieza automática (30 días)
    - Transacciones atómicas
    - Conexión thread-safe
    """

    def __init__(self, db_path: Path, max_records: int = 10000):
        self.db_path = Path(db_path)
        self.max_records = max_records
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
            cursor.execute('''
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
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Índices para rendimiento
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_synced
                ON attendance_records(synced, timestamp)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON attendance_records(timestamp)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id
                ON attendance_records(user_id)
            ''')

            # Deduplicar registros existentes (polls repetidos insertaban el
            # mismo log del dispositivo cada vez) y garantizar idempotencia con
            # un índice único. Clave natural: (user_id, timestamp, device_ip).
            cursor.execute('''
                DELETE FROM attendance_records
                WHERE id NOT IN (
                    SELECT MIN(id) FROM attendance_records
                    GROUP BY user_id, timestamp, device_ip
                )
            ''')

            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance
                ON attendance_records(user_id, timestamp, device_ip)
            ''')

            # Tabla de log de sincronización
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    records_synced INTEGER,
                    records_failed INTEGER,
                    status TEXT,
                    error_message TEXT,
                    duration_seconds REAL
                )
            ''')

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
            cursor.executemany('''
                INSERT OR IGNORE INTO attendance_records
                (user_id, timestamp, status, device_ip, punch_type)
                VALUES (?, ?, ?, ?, ?)
            ''', [
                (
                    r.user_id,
                    r.timestamp.isoformat()
                    if hasattr(r.timestamp, 'isoformat')
                    else str(r.timestamp),
                    r.status,
                    r.device_ip,
                    r.punch_type
                )
                for r in records
            ])

            inserted = cursor.rowcount

            # Limpiar registros antiguos si excedemos el máximo
            self._cleanup_old_records(conn)

            logger.info(
                f"Agregados {inserted} registros al buffer "
                f"({len(records) - inserted} duplicados ignorados)"
            )
            return inserted

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

            cursor.execute('''
                SELECT id, user_id, timestamp, status, device_ip, punch_type
                FROM attendance_records
                WHERE synced = 0
                ORDER BY timestamp ASC, id ASC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'timestamp': row['timestamp'],
                    'status': row['status'],
                    'device_ip': row['device_ip'],
                    'punch_type': row['punch_type'],
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

            placeholders = ','.join('?' * len(record_ids))
            cursor.execute(f'''
                UPDATE attendance_records
                SET synced = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            ''', record_ids)

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

            placeholders = ','.join('?' * len(record_ids))
            cursor.execute(f'''
                UPDATE attendance_records
                SET sync_attempts = sync_attempts + 1,
                    last_sync_attempt = CURRENT_TIMESTAMP,
                    synced = CASE
                        WHEN sync_attempts + 1 >= ? THEN 1
                        ELSE 0
                    END
                WHERE id IN ({placeholders})
            ''', [max_attempts] + record_ids)

    def _cleanup_old_records(self, conn, days: int = 30):
        """
        Limpiar registros antiguos

        Args:
            conn: Conexión SQLite
            days: Días a mantener
        """
        cursor = conn.cursor()

        # Eliminar registros sincronizados mayores a N días
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            DELETE FROM attendance_records
            WHERE synced = 1 AND timestamp < ?
        ''', (cutoff_date,))

        deleted = cursor.rowcount

        # Si aún excedemos el máximo, eliminar los más antiguos
        cursor.execute('SELECT COUNT(*) FROM attendance_records')
        count = cursor.fetchone()[0]

        if count > self.max_records:
            excess = count - self.max_records
            cursor.execute('''
                DELETE FROM attendance_records
                WHERE id IN (
                    SELECT id FROM attendance_records
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
            ''', (excess,))
            deleted += cursor.rowcount

        if deleted > 0:
            logger.info(f"Limpieza completada: {deleted} registros eliminados")

    def get_stats(self) -> dict[str, Any]:
        """
        Obtener estadísticas del buffer

        Returns:
            Dict con estadísticas
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total registros
            cursor.execute('SELECT COUNT(*) FROM attendance_records')
            total = cursor.fetchone()[0]

            # Pendientes de sync
            cursor.execute('SELECT COUNT(*) FROM attendance_records WHERE synced = 0')
            pending = cursor.fetchone()[0]

            # Más antiguo pendiente
            cursor.execute('''
                SELECT MIN(timestamp) FROM attendance_records WHERE synced = 0
            ''')
            oldest_pending = cursor.fetchone()[0]

            # Más reciente
            cursor.execute('SELECT MAX(timestamp) FROM attendance_records')
            newest = cursor.fetchone()[0]

            return {
                'total_records': total,
                'pending_sync': pending,
                'synced': total - pending,
                'oldest_pending': oldest_pending,
                'newest_record': newest,
                'max_records': self.max_records,
                'usage_percent': (total / self.max_records * 100) if self.max_records > 0 else 0
            }

    def log_sync(self, records_synced: int, records_failed: int, status: str,
                 error_message: str | None = None, duration_seconds: float = 0):
        """
        Log de operación de sincronización
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO sync_log
                (records_synced, records_failed, status, error_message, duration_seconds)
                VALUES (?, ?, ?, ?, ?)
            ''', (records_synced, records_failed, status, error_message, duration_seconds))

    def get_sync_history(self, limit: int = 50) -> list[dict]:
        """
        Obtener historial de sincronización
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM sync_log
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def clear_all(self):
        """Limpiar todos los registros (usar con precaución)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM attendance_records')
            cursor.execute('DELETE FROM sync_log')
            logger.warning("Todos los registros del buffer han sido eliminados")
