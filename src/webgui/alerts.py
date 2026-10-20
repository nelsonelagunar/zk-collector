"""
Motor de reglas de alertas HR (MYK-227 / HR-6).

Evaluar los eventos disponibles y generar alertas:
- Incapacidad por vencer (medical_leaves proximas a finalizar)
- Ausencia sin justificar X dias
- N retardos en M dias (reincidencia de retardos)

El envio de email se hace reutilizando src/webgui/mail.py (Mailer).
Las evaluaciones de reglas son funciones puras sobre filas de datos para
poder probarlas con fixtures sin depender de una base de datos real.
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .mail import Mailer, MailError

logger = logging.getLogger(__name__)

# Tipos de regla soportados
RULE_RETARDOS = "retardos_reincidentes"
RULE_INCAPACIDAD = "incapacidad_por_vencer"
RULE_AUSENCIA = "ausencia_sin_justificar"
RULE_VACACIONES = "vacaciones_pendientes"

# Hora de inicio de jornada por defecto (HH:MM)
WORK_START_DEFAULT = "09:00"

# Estado de las alertas
ALERT_STATUS_PENDING = "pending"
ALERT_STATUS_SENT = "sent"
ALERT_STATUS_READ = "read"
ALERT_STATUS_RESOLVED = "resolved"


class AlertEngineError(Exception):
    """Excepcion para errores del motor de alertas."""

    pass


class AlertEngine:
    """
    Motor de reglas de alertas HR.

    Recibe una instancia de Database (webgui.db) y, opcionalmente, un Mailer
    para enviar notificaciones por email.
    """

    def __init__(self, db, mailer: Mailer | None = None):
        self.db = db
        self.mailer = mailer

    # ------------------------------------------------------------------
    # Evaluacion de reglas (logica pura, testable con fixtures)
    # ------------------------------------------------------------------

    def evaluate_retardos_reincidentes(
        self, records: list[dict], n: int, m_days: int, work_start: str = WORK_START_DEFAULT
    ) -> list[dict]:
        """
        Detectar empleados con N retardos en una ventana de M dias.

        Un retardo se cuenta cuando la primera entrada del dia (punch mas
        temprano) ocurre despues de `work_start`.

        Args:
            records: lista de {user_id, timestamp, status, ...}
            n: numero minimo de retardos para disparar
            m_days: ventana de dias (contando atras desde hoy)
            work_start: hora de inicio de jornada "HH:MM"

        Returns:
            lista de {employee_id, event_type, message, event_date}
        """
        if n <= 0 or m_days <= 0:
            return []

        today = date.today()
        cutoff = today - timedelta(days=m_days - 1)

        # Primera entrada por usuario y dia
        first_by_day: dict[tuple[str, str], str] = {}
        for rec in records:
            ts = rec.get("timestamp")
            if not ts:
                continue
            try:
                day = str(ts)[:10]
                record_date = date.fromisoformat(day)
            except (ValueError, TypeError):
                continue
            if record_date < cutoff or record_date > today:
                continue
            time_part = str(ts)[11:16]
            key = (str(rec.get("user_id")), day)
            prev = first_by_day.get(key)
            if prev is None or time_part < prev:
                first_by_day[key] = time_part

        # Contar retardos por usuario dentro de la ventana
        tardy_days: dict[str, list[str]] = {}
        for (user_id, day), time_part in first_by_day.items():
            if time_part > work_start:
                tardy_days.setdefault(user_id, []).append(day)

        alerts = []
        for user_id, days in tardy_days.items():
            if len(days) >= n:
                alerts.append(
                    {
                        "employee_id": user_id,
                        "event_type": RULE_RETARDOS,
                        "message": (
                            f"{len(days)} retardos en {m_days} dias ({', '.join(sorted(days))})"
                        ),
                        "event_date": max(days),
                    }
                )
        return alerts

    def evaluate_incapacidad_por_vencer(self, leaves: list[dict], days_before: int) -> list[dict]:
        """
        Detectar incapacidades activas que vencen en los proximos N dias.

        Args:
            leaves: lista de {employee_id, end_date, status, ...}
            days_before: dias de anticipacion para considerar "por vencer"

        Returns:
            lista de {employee_id, event_type, message, event_date}
        """
        if days_before < 0:
            return []

        today = date.today()
        limit = today + timedelta(days=days_before)

        alerts = []
        for leave in leaves:
            if str(leave.get("status", "")).lower() != "active":
                continue
            end_raw = leave.get("end_date")
            if not end_raw:
                continue
            try:
                end_date = date.fromisoformat(str(end_raw)[:10])
            except (ValueError, TypeError):
                continue
            if today <= end_date <= limit:
                alerts.append(
                    {
                        "employee_id": leave.get("employee_id"),
                        "event_type": RULE_INCAPACIDAD,
                        "message": (f"Incapacidad vence el {end_date.isoformat()}"),
                        "event_date": end_date.isoformat(),
                    }
                )
        return alerts

    def evaluate_ausencia_sin_justificar(self, absences: list[dict], days: int) -> list[dict]:
        """
        Detectar empleados con mas de X ausencias sin justificar.

        Args:
            absences: lista de {employee_id, date, justified, ...}
            days: umbral de ausencias injustificadas para disparar

        Returns:
            lista de {employee_id, event_type, message, event_date}
        """
        if days < 0:
            return []

        unjustified: dict[str, list[str]] = {}
        emp_by_key: dict[str, Any] = {}
        for absence in absences:
            if str(absence.get("justified", "")).lower() in ("1", "true", "yes", "s"):
                continue
            key = str(absence.get("employee_id"))
            unjustified.setdefault(key, []).append(str(absence.get("date")))
            emp_by_key[key] = absence.get("employee_id")

        alerts = []
        for employee_id_key, dates in unjustified.items():
            if len(dates) > days:
                alerts.append(
                    {
                        "employee_id": emp_by_key[employee_id_key],
                        "event_type": RULE_AUSENCIA,
                        "message": (f"{len(dates)} ausencias sin justificar (>{days} dias)"),
                        "event_date": max(d for d in dates if d),
                    }
                )
        return alerts

    # ------------------------------------------------------------------
    # Persistencia y notificacion
    # ------------------------------------------------------------------

    def _now_iso(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    def create_alert(self, rule_id: int, employee_id: int, event_type: str, message: str) -> int:
        """Insertar una alerta y devolver su id."""
        data = {
            "rule_id": rule_id,
            "employee_id": int(employee_id),
            "event_type": event_type,
            "message": message,
            "status": ALERT_STATUS_PENDING,
            "created_at": self._now_iso(),
        }
        return int(self.db.insert("alerts", data))

    def mark_sent(self, alert_id: int) -> None:
        self.db.update(
            "alerts",
            {"status": ALERT_STATUS_SENT, "sent_at": self._now_iso()},
            "id = ?",
            (alert_id,),
        )

    def mark_read(self, alert_id: int) -> None:
        self.db.update(
            "alerts",
            {"status": ALERT_STATUS_READ, "read_at": self._now_iso()},
            "id = ?",
            (alert_id,),
        )

    def mark_resolved(self, alert_id: int) -> None:
        self.db.update(
            "alerts",
            {"status": ALERT_STATUS_RESOLVED, "resolved_at": self._now_iso()},
            "id = ?",
            (alert_id,),
        )

    def _preference_enabled(self, alert_type: str) -> bool:
        """Devuelve True si algun usuario tiene el tipo de alerta opt-in."""
        row = self.db.fetch_one(
            "SELECT 1 FROM user_alert_preferences WHERE alert_type = ? AND enabled = 1 LIMIT 1",
            (alert_type,),
        )
        return row is not None

    def _employee_email(self, employee_id: int) -> str | None:
        employee = self.db.get_employee_by_id(int(employee_id))
        if not employee:
            return None
        return employee.get("email") or None

    def send_alert_email(
        self, alert_id: int, employee_id: int, event_type: str, message: str
    ) -> bool:
        """Enviar email de la alerta si hay mailer y preferencia habilitada.

        Devuelve True si se intento el envio (mailer configurado y preferencia
        activa), False si no correspondia enviar.
        """
        if self.mailer is None:
            logger.info(f"Alerta {alert_id}: sin mailer configurado, email omitido")
            return False
        if not self._preference_enabled(event_type):
            logger.info(f"Alerta {alert_id}: preferencia desactivada para {event_type}")
            return False
        to_email = self._employee_email(employee_id)
        if not to_email:
            logger.warning(f"Alerta {alert_id}: empleado {employee_id} sin email")
            return False

        subject = f"[HR-6] Alerta de evento: {event_type}"
        body = (
            f"Se ha generado una alerta HR para el empleado {employee_id}.\n\n"
            f"Tipo: {event_type}\n"
            f"Detalle: {message}\n\n"
            f"-- Attendance Collector"
        )
        try:
            self.mailer.send(to_email, subject, body)
            self.mark_sent(alert_id)
            logger.info(f"Alerta {alert_id}: email enviado a {to_email}")
            return True
        except MailError as e:
            logger.error(f"Alerta {alert_id}: fallo envio email: {e}")
            return False

    # ------------------------------------------------------------------
    # Orquestacion de reglas
    # ------------------------------------------------------------------

    def run_rule(self, rule: dict) -> list[dict]:
        """
        Ejecutar una regla configurada y persistir las alertas generadas.

        `rule` es una fila de alert_rules: {id, type, enabled, config, ...}.
        `config` es un JSON con los parametros de la regla.
        Returns la lista de alertas creadas.
        """
        if not rule.get("enabled"):
            return []

        rule_id = int(rule["id"])
        rule_type = rule["type"]
        config = json.loads(rule["config"]) if rule.get("config") else {}

        created: list[dict] = []

        if rule_type == RULE_RETARDOS:
            records = self.db.fetch_all("SELECT user_id, timestamp, status FROM attendance_records")
            n = int(config.get("n", 3))
            m_days = int(config.get("m_days", 5))
            work_start = config.get("work_start", WORK_START_DEFAULT)
            candidates = self.evaluate_retardos_reincidentes(records, n, m_days, work_start)

        elif rule_type == RULE_INCAPACIDAD:
            leaves = self.db.fetch_all("SELECT employee_id, end_date, status FROM medical_leaves")
            days_before = int(config.get("days_before", 3))
            candidates = self.evaluate_incapacidad_por_vencer(leaves, days_before)

        elif rule_type == RULE_AUSENCIA:
            absences = self.db.fetch_all("SELECT employee_id, date, justified FROM absences")
            days = int(config.get("days", 3))
            candidates = self.evaluate_ausencia_sin_justificar(absences, days)

        else:
            logger.warning(f"Regla {rule_id}: tipo desconocido {rule_type}")
            return []

        for candidate in candidates:
            employee_id = candidate["employee_id"]
            alert_id = self.create_alert(
                rule_id, employee_id, candidate["event_type"], candidate["message"]
            )
            created.append(
                {
                    "id": alert_id,
                    "employee_id": employee_id,
                    "event_type": candidate["event_type"],
                    "message": candidate["message"],
                }
            )
            # Intentar notificar por email
            self.send_alert_email(
                alert_id, employee_id, candidate["event_type"], candidate["message"]
            )

        logger.info(f"Regla {rule_id} ({rule_type}): {len(created)} alerta(s) creada(s)")
        return created

    def run_all(self) -> dict[str, list[dict]]:
        """Ejecutar todas las reglas habilitadas. Devuelve {type: alertas}."""
        rules = self.db.fetch_all("SELECT * FROM alert_rules WHERE enabled = 1")
        results: dict[str, list[dict]] = {}
        for rule in rules:
            created = self.run_rule(rule)
            results[rule["type"]] = created
        return results
