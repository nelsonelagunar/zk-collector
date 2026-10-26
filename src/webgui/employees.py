"""
Employee data access layer - Colaboradores module (Sprint 3, MYK-220)

CRUD basico sobre las tablas `employees` y `employee_device_links`.
Contrato consumido por la API REST `/api/employees` (backend-dev, MYK-221).

Nota sobre integridad referencial: las FK se declaran en la migracion 002,
pero SQLite las desactiva por defecto por conexion (`PRAGMA foreign_keys`).
Por eso `delete()` limpia los links explicitamente antes de borrar el empleado.
"""

import logging
from datetime import datetime

from .database import Database
from .validators import normalize_labor_fields

logger = logging.getLogger(__name__)

VALID_STATUSES = ("active", "inactive")


class EmployeeRepository:
    """Acceso a datos de colaboradores sobre la instancia `Database` de webgui."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _validate_status(status: str | None) -> None:
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"status invalido: {status!r} (esperado {VALID_STATUSES})")

    def create(self, data: dict) -> int:
        """Crear colaborador. Requiere `employee_code`. Retorna el id."""
        if not data.get("employee_code"):
            raise ValueError("employee_code es requerido")
        self._validate_status(data.get("status"))
        normalize_labor_fields(data)

        now = datetime.now().isoformat()
        payload = dict(data)
        payload.setdefault("status", "active")
        payload["created_at"] = now
        payload["updated_at"] = now
        return self.db.insert("employees", payload)

    def get(self, employee_id: int) -> dict | None:
        return self.db.fetch_one("SELECT * FROM employees WHERE id = ?", (employee_id,))

    def get_by_code(self, employee_code: str) -> dict | None:
        return self.db.fetch_one(
            "SELECT * FROM employees WHERE employee_code = ?", (employee_code,)
        )

    def list_employees(self, status: str | None = None, search: str | None = None) -> list[dict]:
        """Listar colaboradores, con filtro opcional por status y busqueda libre."""
        self._validate_status(status)

        where = []
        params: list[object] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if search:
            where.append(
                "(first_name LIKE ? OR last_name LIKE ? OR employee_code LIKE ? OR email LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return self.db.fetch_all(
            f"SELECT * FROM employees {clause} ORDER BY employee_code", tuple(params)
        )

    def update(self, employee_id: int, data: dict) -> int:
        """Actualizar campos editables. `employee_code` y `created_at` no se modifican."""
        self._validate_status(data.get("status"))
        normalize_labor_fields(data)

        payload = {k: v for k, v in data.items() if k not in ("id", "employee_code", "created_at")}
        payload["updated_at"] = datetime.now().isoformat()
        return self.db.update("employees", payload, "id = ?", (employee_id,))

    def set_status(self, employee_id: int, status: str) -> int:
        """Baja/alta logica del colaborador (status active/inactive)."""
        self._validate_status(status)
        return self.db.update(
            "employees",
            {"status": status, "updated_at": datetime.now().isoformat()},
            "id = ?",
            (employee_id,),
        )

    def delete(self, employee_id: int) -> int:
        """Borrado fisico; limpia los links antes (cascade explicito, FK off-safe)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM employee_device_links WHERE employee_id = ?", (employee_id,))
            cursor = conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            return cursor.rowcount if cursor.rowcount is not None else 0

    def link_device(self, employee_id: int, device_serial: str, device_user_id: str) -> int:
        """Vincular un badge/device al colaborador. Idempotente (UNIQUE del par serial+user_id)."""
        if not device_serial or not device_user_id:
            raise ValueError("device_serial y device_user_id son requeridos")

        now = datetime.now().isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO employee_device_links
                    (employee_id, device_serial, device_user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (employee_id, device_serial, device_user_id, now, now),
            )
            return cursor.rowcount if cursor.rowcount is not None else 0

    def unlink_device(self, employee_id: int, device_serial: str, device_user_id: str) -> int:
        return self.db.delete(
            "employee_device_links",
            "employee_id = ? AND device_serial = ? AND device_user_id = ?",
            (employee_id, device_serial, device_user_id),
        )

    def list_links(self, employee_id: int) -> list[dict]:
        return self.db.fetch_all(
            "SELECT * FROM employee_device_links WHERE employee_id = ? ORDER BY id",
            (employee_id,),
        )
