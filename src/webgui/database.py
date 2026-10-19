"""
Database Module - Attendance Collector
Manejo de base de datos SQLite
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Database:
    """
    Manejo de base de datos SQLite con:
    - Connection pooling básico
    - Migraciones automáticas
    - Context managers para transacciones
    - Métodos específicos para tablas de empleados
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

            # Obtener migraciones aplicadas
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM _migrations")
            applied = {row["name"] for row in cursor.fetchall()}

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
                cursor.execute("INSERT INTO _migrations (name) VALUES (?)", (migration_name,))

            logger.info(f"Migraciones completadas: {len(migration_files)} archivos")

    # Métodos genéricos
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

    # Métodos específicos para empleados
    def get_employee_by_code(self, employee_code: str) -> dict | None:
        """Obtener empleado por código"""
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

    # Métodos específicos para enlaces empleado-dispositivo
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
