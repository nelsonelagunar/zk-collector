"""
Database Module - Attendance Collector
Manejo de base de datos SQLite
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Database:
    """
    Manejo de base de datos SQLite con:
    - Connection pooling básico
    - Migraciones automáticas
    - Context managers para transacciones
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None

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

    def initialize(self):
        """Inicializar base de datos con migraciones"""
        logger.info(f"Inicializando base de datos: {self.db_path}")
        self._run_migrations()

    def _find_migrations_dir(self) -> Path | None:
        """Localizar el directorio de migraciones.

        Orden: MIGRATIONS_DIR env > <db_path>/../../migrations (layout del
        contenedor: /app/data/webgui.db -> /app/migrations) > raíz del repo.
        """
        env_dir = os.environ.get("MIGRATIONS_DIR")
        if env_dir:
            path = Path(env_dir)
            if path.exists():
                return path

        candidates = [
            self.db_path.parent.parent / "migrations",
            Path(__file__).resolve().parents[2] / "migrations",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _run_migrations(self):
        """Ejecutar migraciones pendientes"""
        migrations_dir = self._find_migrations_dir()

        if not migrations_dir:
            logger.warning("Directorio de migraciones no encontrado")
            return

        migration_files = sorted(migrations_dir.glob("*.sql"))

        with self.get_connection() as conn:
            # Crear tabla de migraciones si no existe
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Obtener migraciones aplicadas
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM _migrations")
            applied = {row['name'] for row in cursor.fetchall()}

            # Aplicar migraciones pendientes
            for migration_file in migration_files:
                migration_name = migration_file.name

                if migration_name in applied:
                    logger.debug(f"Migration {migration_name} ya aplicada")
                    continue

                logger.info(f"Aplicando migration: {migration_name}")

                with open(migration_file) as f:
                    sql = f.read()

                conn.executescript(sql)
                cursor.execute(
                    "INSERT INTO _migrations (name) VALUES (?)",
                    (migration_name,)
                )

            logger.info(f"Migraciones completadas: {len(migration_files)} archivos")

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Ejecutar query simple"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Obtener un registro"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Obtener múltiples registros"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def insert(self, table: str, data: dict) -> int:
        """Insertar registro"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))

        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid if cursor.lastrowid is not None else 0

    def update(self, table: str, data: dict, where: str, where_params: tuple = ()) -> int:
        """Actualizar registros"""
        set_clause = ', '.join([f"{k} = ?" for k in data])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"

        params = tuple(data.values()) + where_params

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount if cursor.rowcount is not None else 0

    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        """Eliminar registros"""
        query = f"DELETE FROM {table} WHERE {where}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, where_params)
            return cursor.rowcount if cursor.rowcount is not None else 0
