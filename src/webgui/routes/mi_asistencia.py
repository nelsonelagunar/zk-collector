"""Rutas del portal del trabajador /mi-asistencia (MYK-425, MYK-410 item 7).

Lectura-unica de las marcas y horas extra del periodo del PROPIO empleado
(derecho LFT 132-XVII). Autenticacion por PIN por empleado (Argon2id,
migracion 009). Aislamiento obligatorio: todo query param `employee_id`
distinto al de sesion responde 403 — nunca se exponen registros ajenos.
Aviso de privacidad enlazado (datos biometricos = sensibles LFPDPPP).
"""

import re
import time
from collections import defaultdict
from threading import Lock
from typing import cast

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..database import Database
from ..portal import (
    DEFAULT_WORK_START,
    PortalValidationError,
    build_day_rows,
    default_period,
    fetch_own_records,
    get_employee_link_pairs,
    parse_period,
    period_quick_links,
    summarize_period,
)

mi_asistencia_bp = Blueprint("mi_asistencia", __name__)

SESSION_EMPLOYEE_KEY = "portal_employee_id"
PIN_PATTERN = re.compile(r"^\d{4,8}$")

# Rate limiting del PIN: 5 intentos fallidos por 15 min por codigo de empleado
PIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
PIN_RATE_LIMIT_MAX_ATTEMPTS = 5

_pin_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_pin_rate_limit_lock = Lock()


def _check_pin_rate_limit(employee_code: str) -> bool:
    """Registra un intento; False si el codigo ya agoto el limite."""
    now = time.time()
    key = employee_code.lower().strip()
    with _pin_rate_limit_lock:
        _pin_rate_limit_store[key] = [
            t for t in _pin_rate_limit_store[key] if now - t < PIN_RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(_pin_rate_limit_store[key]) >= PIN_RATE_LIMIT_MAX_ATTEMPTS:
            return False
        _pin_rate_limit_store[key].append(now)
        return True


def reset_pin_rate_limit_store() -> None:
    """Limpia el rate limiter (para tests)."""
    with _pin_rate_limit_lock:
        _pin_rate_limit_store.clear()


def _current_portal_employee() -> dict | None:
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employee_id = session.get(SESSION_EMPLOYEE_KEY)
    if employee_id is None:
        return None
    return db.get_employee_by_id(employee_id)


def _enforce_own_employee_id() -> None:
    """AC MYK-425: `employee_id` ajeno en query args -> 403 inmediato."""
    requested = request.args.get("employee_id")
    if not requested:
        return
    try:
        requested_id = int(requested)
    except ValueError:
        abort(403)
    if requested_id != session.get(SESSION_EMPLOYEE_KEY):
        abort(403)


def _work_start() -> str:
    value = current_app.config.get("ATTENDANCE_WORK_START", DEFAULT_WORK_START)
    return str(value)


@mi_asistencia_bp.route("/login", methods=["GET", "POST"])
def portal_login():
    """Login del trabajador: numero de empleado + PIN."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    if session.get(SESSION_EMPLOYEE_KEY) and _current_portal_employee():
        return redirect(url_for("mi_asistencia.portal_index"))

    if request.method == "POST":
        employee_code = (request.form.get("employee_code", "") or "").strip()
        pin = (request.form.get("pin", "") or "").strip()

        if not _check_pin_rate_limit(employee_code):
            flash("Demasiados intentos. Espera 15 minutos e intentalo de nuevo.", "error")
            return render_template("mi_asistencia/login.html"), 429

        # Mensaje generico unico (anti-enumeracion): no revela si el codigo
        # existe, si tiene PIN o si esta inactivo.
        def _invalid():
            flash("Numero de empleado o PIN incorrecto.", "error")
            return render_template("mi_asistencia/login.html"), 401

        if not employee_code or not PIN_PATTERN.match(pin):
            return _invalid()

        employee = db.fetch_one(
            "SELECT id, employee_code, first_name, last_name, pin_hash, status "
            "FROM employees WHERE employee_code = ?",
            (employee_code,),
        )
        if not employee or not employee["pin_hash"] or employee["status"] != "active":
            return _invalid()

        if not current_app.auth.verify_password(pin, employee["pin_hash"]):  # type: ignore[attr-defined]
            return _invalid()

        session.clear()
        session[SESSION_EMPLOYEE_KEY] = employee["id"]
        session["portal_employee_code"] = employee["employee_code"]
        session["portal_employee_name"] = (
            f"{employee['first_name']} {employee['last_name']}".strip()
        )
        flash(f"Bienvenido, {session['portal_employee_name']}!", "success")
        return redirect(url_for("mi_asistencia.portal_index"))

    return render_template("mi_asistencia/login.html")


@mi_asistencia_bp.route("/logout")
def portal_logout():
    """Cierra la sesion del portal (solo las claves del portal)."""
    session.pop(SESSION_EMPLOYEE_KEY, None)
    session.pop("portal_employee_code", None)
    session.pop("portal_employee_name", None)
    flash("Sesion del portal cerrada.", "info")
    return redirect(url_for("mi_asistencia.portal_login"))


@mi_asistencia_bp.route("/aviso-privacidad")
def portal_privacy():
    """Aviso de privacidad del portal (datos biometricos = sensibles LFPDPPP)."""
    return render_template("mi_asistencia/aviso_privacidad.html")


@mi_asistencia_bp.route("/", strict_slashes=False)
def portal_index():
    """Consulta lectura-unica de las marcas y horas extra del periodo propio."""
    employee = _current_portal_employee()
    if not employee:
        return redirect(url_for("mi_asistencia.portal_login"))
    _enforce_own_employee_id()

    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    start, end = default_period()
    if request.args.get("start_date") or request.args.get("end_date"):
        try:
            start, end = parse_period(request.args.get("start_date"), request.args.get("end_date"))
        except PortalValidationError as exc:
            flash(str(exc), "error")

    pairs = get_employee_link_pairs(db, employee["id"])
    records = fetch_own_records(current_app.buffer_repo, pairs, start, end)  # type: ignore[attr-defined]
    day_rows = build_day_rows(records, _work_start())
    summary = summarize_period(day_rows)

    return render_template(
        "mi_asistencia/index.html",
        employee=employee,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        day_rows=day_rows,
        summary=summary,
        quick_links=period_quick_links(),
    )


@mi_asistencia_bp.route("/api/records")
def portal_api_records():
    """JSON de las marcas propias del periodo. `employee_id` ajeno -> 403."""
    employee = _current_portal_employee()
    if not employee:
        return jsonify({"error": "autenticacion requerida"}), 401
    _enforce_own_employee_id()

    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    start, end = default_period()
    try:
        if request.args.get("start_date") or request.args.get("end_date"):
            start, end = parse_period(request.args.get("start_date"), request.args.get("end_date"))
        pairs = get_employee_link_pairs(db, employee["id"])
        records = fetch_own_records(current_app.buffer_repo, pairs, start, end)  # type: ignore[attr-defined]
        day_rows = build_day_rows(records, _work_start())
        summary = summarize_period(day_rows)
    except PortalValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "employee": {
                "employee_id": employee["id"],
                "employee_code": employee["employee_code"],
                "employee_name": f"{employee['first_name']} {employee['last_name']}".strip(),
            },
            "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
            "summary": summary,
            "days": day_rows,
        }
    )
