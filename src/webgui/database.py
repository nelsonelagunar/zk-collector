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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        if not cursor.fetchone():
            return  # Table doesnt exist yet, migrations will create it correctly

        # Get current columns
        cursor.execute("PRAGMA table_info(devices)")
        columns = {row[1] for row in cursor.fetchall()}

        has_ip = "ip" in columns
        has_address = "address" in columns

        # If we have old schema (ip, enabled) but not new schema (address, is_enabled)
        if has_ip and not has_address:
            logger.info(
                "Detected old devices schema (ip, enabled). Migrating to new schema "
                "(address, is_enabled)..."
            )

            # Create new table with correct schema
            conn.execute("""
                CREATE TABLE devices_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    location TEXT,
                    zone TEXT,
                    address TEXT NOT NULL DEFAULT ,
                    port INTEGER DEFAULT 4370,
                    password INTEGER DEFAULT 0,
                    timeout INTEGER DEFAULT 5,
                    protocol TEXT DEFAULT tcp,
                    status TEXT DEFAULT unknown,
                    is_enabled BOOLEAN DEFAULT 1,
                    firmware_version TEXT,
                    serial_number TEXT,
                    last_seen DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Copy data from old to new
            conn.execute("""
                INSERT INTO devices_new (
                    id, name, location, zone, address, port, password, timeout,
                    protocol, status, is_enabled, firmware_version, serial_number,
                    last_seen, created_at, updated_at
                )
                SELECT
                    id, name,
                    location, zone,
                    ip as address,
                    port,
                    CASE
                        WHEN typeof(password) = text THEN CAST(password AS INTEGER)
                        ELSE password
                    END as password,
                    timeout,
                    protocol,
                    status,
                    enabled as is_enabled,
                    firmware_version,
                    serial_number,
                    last_seen,
                    created_at,
                    updated_at
                FROM devices
            """)

            # Replace old table
            conn.execute("DROP TABLE devices")
            conn.execute("ALTER TABLE devices_new RENAME TO devices")

            # Recreate indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_address ON devices(address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status)")

            logger.info("Devices schema migration completed successfully")

        # Also fix device_users table if it has old schema (device_ip instead of device_id)
        cursor.execute("PRAGMA table_info(device_users)")
        du_columns = {row[1] for row in cursor.fetchall()}

        if "device_ip" in du_columns and "device_id" not in du_columns:
            logger.info(
                "Detected old device_users schema (device_ip). Migrating to new schema "
                "(device_id FK)..."
            )

            conn.execute("""
                CREATE TABLE device_users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    name TEXT,
                    privilege INTEGER DEFAULT 0,
                    password TEXT,
                    group_id TEXT,
                    user_role TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
                )
            """)

            # Map device_ip to device_id
            conn.execute("""
                INSERT INTO device_users_new (
                    id, device_id, user_id, name, privilege, password,
                    group_id, user_role, created_at, updated_at
                )
                SELECT
                    du.id,
                    d.id as device_id,
                    du.user_id,
                    du.name,
                    du.privilege,
                    du.password,
                    CAST(du.group_id AS TEXT) as group_id,
                    du.user_role,
                    du.created_at,
                    du.updated_at
                FROM device_users du
                JOIN devices d ON d.address = du.device_ip
            """)

            conn.execute("DROP TABLE device_users")
            conn.execute("ALTER TABLE device_users_new RENAME TO device_users")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_device_users_device_id "
                "ON device_users(device_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_device_users_user_id "
                "ON device_users(user_id)"
            )

            logger.info("Device_users schema migration completed successfully")

    # Metodos genericos
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
        """Obtener multiples registros"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def insert(self, table: str, data: dict) -> int:
        """Insertar registro"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))

        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid if cursor.lastrowid is not None else 0

    def update(self, table: str, data: dict, where: str, where_params: tuple = ()) -> int:
        """Actualizar registros"""
        set_clause = ", ".join([f"{k} = ?" for k in data])
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

    # Metodos especificos para empleados
    def get_employee_by_code(self, employee_code: str) -> dict | None:
        """Obtener empleado por codigo"""
        return self.fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))

    def get_employee_by_id(self, employee_id: int) -> dict | None:
        """Obtener empleado por ID"""
        return self.fetch_one("SELECT * FROM employees WHERE id = ?", (employee_id,))

    def get_employees(self, status: str | None = None, department: str | None = None) -> list[dict]:
        """Obtener lista de empleados con filtros opcionales"""
        query = "SELECT * FROM employees"
        params = []

        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if department:
            conditions.append("department = ?")
            params.append(department)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY last_name, first_name"

        return self.fetch_all(query, tuple(params))

    def create_employee(self, employee_data: dict) -> int:
        """Crear nuevo empleado. created_at/updated_at usan DEFAULT CURRENT_TIMESTAMP."""
        return self.insert("employees", employee_data)

    def update_employee(self, employee_id: int, employee_data: dict) -> int:
        """Actualizar empleado existente; refresca updated_at."""
        employee_data = dict(employee_data)
        employee_data["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        return self.update("employees", employee_data, "id = ?", (employee_id,))

    def delete_employee(self, employee_id: int) -> int:
        """Eliminar empleado (soft delete mediante status)"""
        return self.update(
            "employees",
            {
                "status": "inactive",
                "updated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            },
            "id = ?",
            (employee_id,),
        )

    # Metodos especificos para enlaces empleado-dispositivo
    def link_employee_to_device(
        self, employee_id: int, device_serial: str, device_user_id: str
    ) -> int:
        """Vincular empleado con dispositivo"""
        link_data = {
            "employee_id": employee_id,
            "device_serial": device_serial,
            "device_user_id": device_user_id,
        }
        return self.insert("employee_device_links", link_data)

    def unlink_employee_from_device(
        self, employee_id: int, device_serial: str, device_user_id: str
    ) -> int:
        """Desvincular empleado de dispositivo"""
        return self.delete(
            "employee_device_links",
            "employee_id = ? AND device_serial = ? AND device_user_id = ?",
            (employee_id, device_serial, device_user_id),
        )

    def get_devices_for_employee(self, employee_id: int) -> list[dict]:
        """Obtener dispositivos vinculados a un empleado"""
        return self.fetch_all(
            """
            SELECT edl.*, d.name as device_name, d.location, d.address
            FROM employee_device_links edl
            JOIN devices d ON edl.device_serial = d.serial_number
            WHERE edl.employee_id = ?
        """,
            (employee_id,),
        )

    def get_employees_for_device(self, device_serial: str, device_user_id: str) -> list[dict]:
        """Obtener empleados vinculados a un dispositivo"""
        return self.fetch_all(
            """
            SELECT e.*, edl.device_serial, edl.device_user_id
            FROM employee_device_links edl
            JOIN employees e ON edl.employee_id = e.id
            WHERE edl.device_serial = ? AND edl.device_user_id = ?
        """,
            (device_serial, device_user_id),
        )

    # Metodos especificos para razones sociales (empresas) -- MYK-405, migration 008
    def get_company_by_id(self, company_id: int) -> dict | None:
        """Obtener empresa por ID"""
        return self.fetch_one("SELECT * FROM companies WHERE id = ?", (company_id,))

    def get_company_by_rfc(self, rfc: str) -> dict | None:
        """Obtener empresa activa por RFC"""
        return self.fetch_one("SELECT * FROM companies WHERE rfc = ? AND status = 'active'", (rfc,))

    def get_companies(self, status: str | None = None) -> list[dict]:
        """Obtener lista de empresas con filtro opcional de status"""
        if status:
            return self.fetch_all(
                "SELECT * FROM companies WHERE status = ? ORDER BY razon_social", (status,)
            )
        return self.fetch_all("SELECT * FROM companies ORDER BY razon_social")

    def create_company(self, company_data: dict) -> int:
        """Crear nueva empresa (razon social); razon_social es obligatorio."""
        return self.insert("companies", company_data)

    def update_company(self, company_id: int, company_data: dict) -> int:
        """Actualizar empresa existente; refresca updated_at."""
        company_data = dict(company_data)
        company_data["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        return self.update("companies", company_data, "id = ?", (company_id,))

    def delete_company(self, company_id: int) -> int:
        """Eliminar empresa (soft delete mediante status); conserva vinculos."""
        return self.update(
            "companies",
            {
                "status": "inactive",
                "updated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            },
            "id = ?",
            (company_id,),
        )

    # Metodos especificos para el vinculo empresa <-> reloj checador
    def link_device_to_company(self, company_id: int, device_serial: str) -> int:
        """Vincular reloj a empresa (1:N): upsert -- re-vincular transfiere la propiedad."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO company_devices (company_id, device_serial)
                VALUES (?, ?)
                ON CONFLICT(device_serial) DO UPDATE SET
                    company_id = excluded.company_id,
                    updated_at = excluded.updated_at
            """,
                (company_id, device_serial),
            )
            return cursor.lastrowid if cursor.lastrowid is not None else 0

    def unlink_device_from_company(self, device_serial: str) -> int:
        """Desvincular reloj de su empresa"""
        return self.delete("company_devices", "device_serial = ?", (device_serial,))

    def get_devices_for_company(self, company_id: int) -> list[dict]:
        """Obtener relojes vinculados a una empresa"""
        return self.fetch_all(
            """
            SELECT cd.*, d.name as device_name, d.location, d.address
            FROM company_devices cd
            LEFT JOIN devices d ON cd.device_serial = d.serial_number
            WHERE cd.company_id = ?
            ORDER BY cd.device_serial
        """,
            (company_id,),
        )

    def get_company_for_device(self, device_serial: str) -> dict | None:
        """Obtener la empresa propietaria de un reloj (1:N: maximo una)"""
        return self.fetch_one(
            """
            SELECT c.*, cd.device_serial
            FROM company_devices cd
            JOIN companies c ON cd.company_id = c.id
            WHERE cd.device_serial = ?
        """,
            (device_serial,),
        )
