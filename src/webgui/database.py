"""
Database Module - Attendance Collector
Manejo de base de datos SQLite
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Database:
    """
    Manejo de base de datos SQLite con:
    - Connection pooling basico
    - Migraciones automaticas
    - Context managers para transacciones
    - Metodos especificos para tablas de empleados
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

    def _run_migrations(self):
        """Ejecutar migraciones pendientes"""
        migrations_dir = self.db_path.parent.parent / "migrations"

        if not migrations_dir.exists():
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

            # FIX SCHEMA TRANSITION: Handle devices table old -> new schema
            # Some live databases have the old schema (ip, enabled) from earlier
            # migrations (003_device_columns.sql) while 001_initial_schema.sql
            # now defines the new schema (address, is_enabled).
            # We fix this BEFORE running migrations to avoid "no such column" errors.
            self._fix_devices_schema_transition(conn)

            # Obtener migraciones aplicadas
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM _migrations")
            applied = {row["name"] for row in cursor.fetchall()}

            # Aplicar migraciones pendientes
            for migration_file in migration_files:
                migration_name = migration_file.name

                # Seeds de datos demo (*_demo_seed*.sql) son opt-in: solo
                # aplican con ZK_DEMO_SEED=1 (default en Docker, MYK-377).
                if "_demo_seed" in migration_name and os.environ.get("ZK_DEMO_SEED") != "1":
                    logger.debug(
                        f"Migration {migration_name} omitida (ZK_DEMO_SEED != 1)"
                    )
                    continue

                if migration_name in applied:
                    logger.debug(f"Migration {migration_name} ya aplicada")
                    continue

                logger.info(f"Aplicando migration: {migration_name}")

                with open(migration_file) as f:
                    sql = f.read()

                conn.executescript(sql)
                cursor.execute("INSERT INTO _migrations (name) VALUES (?)", (migration_name,))

            logger.info(f"Migraciones completadas: {len(migration_files)} archivos")

    def _fix_devices_schema_transition(self, conn):
        """
        Fix devices table schema transition from old (ip, enabled) to new (address, is_enabled).
        
        Some live databases were created with the old schema from migration 003_device_columns.sql
        which added columns to a table with ip and enabled columns. The new 001_initial_schema.sql
        defines address and is_enabled instead. This causes "no such column: ip" errors
        when later migrations reference the old column names.
        
        We detect and fix this by rebuilding the table with the correct schema.
        """
        cursor = conn.cursor()
        
        # Check if devices table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type=table AND name=devices")
        if not cursor.fetchone():
            return  # Table doesnt exist yet, migrations will create it correctly
