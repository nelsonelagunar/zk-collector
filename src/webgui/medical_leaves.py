"""
Medical leaves data access layer - Incapacidades (Sprint 3, MYK-238/MYK-239)

Acceso a datos sobre la tabla `medical_leaves`.
Contrato consumido por la API REST `/api/medical-leaves` (backend-dev, MYK-239).

Reglas:
- `days` se calcula siempre server-side = (end_date - start_date).days + 1.
- `leave_type` debe pertenecer al enum del schema.
- El traslape con vacaciones aprobadas NO bloquea: genera warnings aislados.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta

from .database import Database

VALID_LEAVE_TYPES = ("enfermedad", "maternidad", "accidente", "otro")


class ValidationError(ValueError):
    """Error de validacion de payload."""


class EmployeeNotFoundError(LookupError):
    """El employee_id referenciado no existe."""


class LeaveNotFoundError(LookupError):
    """La incapacidad referenciada no existe."""


class MedicalLeaveRepository:
    """Acceso a datos de incapacidades sobre la instancia `Database` de webgui."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _parse_date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value if value is not None else "").strip()
        if not text:
            raise ValidationError("fecha requerida")
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValidationError(f"fecha invalida: {text!r}") from exc

    @staticmethod
    def _normalize_document_ref(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _require_employee(self, employee_id: int) -> None:
        if not self.db.get_employee_by_id(employee_id):
            raise EmployeeNotFoundError(f"empleado no encontrado: {employee_id}")

    @staticmethod
    def _validate_leave_type(leave_type: str) -> None:
        if leave_type not in VALID_LEAVE_TYPES:
            raise ValidationError(f"leave_type invalido: {leave_type!r}")

    def create(self, data: dict) -> int:
        """Crear incapacidad. Retorna el id. Ignora `days` del cliente."""
        if "employee_id" not in data or data["employee_id"] is None:
            raise ValidationError("employee_id es requerido")
        try:
            employee_id = int(data["employee_id"])
        except (TypeError, ValueError) as exc:
            raise ValidationError("employee_id invalido") from exc

        self._require_employee(employee_id)

        leave_type = str(data.get("leave_type", "")).strip()
        self._validate_leave_type(leave_type)

        start_date = self._parse_date(data.get("start_date"))
        end_date = self._parse_date(data.get("end_date"))
        if end_date < start_date:
            raise ValidationError("end_date debe ser >= start_date")

        days = (end_date - start_date).days + 1
        payload = {
            "employee_id": employee_id,
            "leave_type": leave_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "doctor_name": data.get("doctor_name"),
            "document_ref": self._normalize_document_ref(data.get("document_ref")),
        }
        return self.db.insert("medical_leaves", payload)

    def get(self, leave_id: int) -> dict | None:
        return self.db.fetch_one("SELECT * FROM medical_leaves WHERE id = ?", (leave_id,))

    def list_leaves(
        self,
        employee_id: int | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[dict], int]:
        """Listar incapacidades activas y canceladas con paginación opcional."""
        conditions: list[str] = []
        params: list[object] = []

        if employee_id is not None:
            conditions.append("employee_id = ?")
            params.append(employee_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        total_row = self.db.fetch_one(
            f"SELECT COUNT(*) AS total FROM medical_leaves {where}", tuple(params)
        )
        total = total_row["total"] if total_row else 0

        offset = max(0, (page - 1) * per_page)
        rows = self.db.fetch_all(
            f"SELECT * FROM medical_leaves {where} "
            "ORDER BY start_date DESC, id DESC LIMIT ? OFFSET ?",
            tuple(params + [per_page, offset]),
        )
        return rows, total

    def update(self, leave_id: int, data: dict) -> int:
        """Actualizar campos editables. `days` se recalcula server-side."""
        row = self.get(leave_id)
        if not row:
            raise LeaveNotFoundError(f"incapacidad no encontrada: {leave_id}")

        if "employee_id" in data and data["employee_id"] is not None:
            try:
                new_employee_id = int(data["employee_id"])
            except (TypeError, ValueError) as exc:
                raise ValidationError("employee_id invalido") from exc
            if new_employee_id != row["employee_id"]:
                self._require_employee(new_employee_id)
        else:
            new_employee_id = row["employee_id"]

        leave_type = row["leave_type"]
        if "leave_type" in data and data["leave_type"] is not None:
            leave_type = str(data["leave_type"]).strip()
            self._validate_leave_type(leave_type)

        if "start_date" in data and data["start_date"] is not None:
            start_date = self._parse_date(data["start_date"])
        else:
            start_date = self._parse_date(row["start_date"])

        if "end_date" in data and data["end_date"] is not None:
            end_date = self._parse_date(data["end_date"])
        else:
            end_date = self._parse_date(row["end_date"])

        if end_date < start_date:
            raise ValidationError("end_date debe ser >= start_date")

        days = (end_date - start_date).days + 1

        payload = {
            "employee_id": new_employee_id,
            "leave_type": leave_type,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "updated_at": datetime.now().isoformat(),
        }

        if "doctor_name" in data and data["doctor_name"] is not None:
            payload["doctor_name"] = data["doctor_name"]
        if "document_ref" in data and data["document_ref"] is not None:
            payload["document_ref"] = self._normalize_document_ref(data["document_ref"])

        return self.db.update("medical_leaves", payload, "id = ?", (leave_id,))

    def cancel(self, leave_id: int) -> int:
        """Borrado lógico: status -> cancelled."""
        return self.db.update(
            "medical_leaves",
            {"status": "cancelled", "updated_at": datetime.now().isoformat()},
            "id = ?",
            (leave_id,),
        )

    def get_leave_dates(self, employee_id: int, desde: object, hasta: object) -> list[str]:
        """Fechas con incapacidad activa para un empleado dentro de [desde, hasta]."""
        start = self._parse_date(desde)
        end = self._parse_date(hasta)
        if end < start:
            raise ValidationError("hasta debe ser >= desde")

        rows = self.db.fetch_all(
            "SELECT start_date, end_date FROM medical_leaves "
            "WHERE employee_id = ? AND status = 'active' "
            "AND start_date <= ? AND end_date >= ? "
            "ORDER BY start_date",
            (employee_id, end.isoformat(), start.isoformat()),
        )

        dates: set[str] = set()
        for row in rows:
            row_start = self._parse_date(row["start_date"])
            row_end = self._parse_date(row["end_date"])
            current = max(row_start, start)
            final = min(row_end, end)
            while current <= final:
                dates.add(current.isoformat())
                current += timedelta(days=1)
        return sorted(dates)

    def vacation_overlap_warnings(
        self, employee_id: int, start_date: object, end_date: object
    ) -> list[str]:
        """Warnings por traslape con vacaciones aprobadas. Tabla inexistente -> sin warning."""
        table = self.db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'vacation_requests'"
        )
        if not table:
            return []

        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        try:
            rows = self.db.fetch_all(
                "SELECT * FROM vacation_requests "
                "WHERE employee_id = ? AND status = 'approved' "
                "AND start_date <= ? AND end_date >= ? "
                "ORDER BY start_date",
                (employee_id, end.isoformat(), start.isoformat()),
            )
        except sqlite3.OperationalError:
            return []

        warnings: list[str] = []
        for row in rows:
            warnings.append(
                "La incapacidad se traslada con vacaciones aprobadas "
                f"del {row['start_date']} al {row['end_date']}"
            )
        return warnings
