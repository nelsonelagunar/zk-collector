"""
Settings UI Routes - Seccion Configuracion (MYK-377).

Muestra y edita system_config dentro del layout con menus. smtp_password
nunca se muestra (write-only); el resto de claves SMTP y company_name son
editables por el admin.
"""

from datetime import datetime
from typing import cast

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..database import Database
from ..middleware.auth import admin_required, login_required

settings_ui_bp = Blueprint("settings_ui", __name__)

# Claves que el form puede actualizar (smtp_password va aparte: write-only)
EDITABLE_KEYS = (
    "company_name",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_from_email",
    "smtp_use_tls",
)


@settings_ui_bp.route("/", strict_slashes=False)
@login_required
def settings_ui():
    """Pagina de configuracion del sistema."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    rows = db.fetch_all(
        "SELECT key, value, description, updated_at FROM system_config ORDER BY key"
    )
    settings = {row["key"]: row for row in rows}
    return render_template("settings/index.html", settings=settings, editable_keys=EDITABLE_KEYS)


@settings_ui_bp.route("/update", methods=["POST"], strict_slashes=False)
@admin_required
def settings_update():
    """Actualiza las claves editables de system_config (solo admin)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    for key in EDITABLE_KEYS:
        if key not in request.form:
            continue
        value = request.form.get(key, "").strip()
        db.update(
            "system_config",
            {"value": value, "updated_at": datetime.now().isoformat()},
            "key = ?",
            (key,),
        )

    smtp_password = request.form.get("smtp_password", "")
    if smtp_password:
        db.update(
            "system_config",
            {"value": smtp_password, "updated_at": datetime.now().isoformat()},
            "key = ?",
            ("smtp_password",),
        )

    existing_pw = db.fetch_one("SELECT value FROM system_config WHERE key = 'smtp_password'")
    has_password = bool(smtp_password) or bool(existing_pw and existing_pw.get("value"))
    host = db.fetch_one("SELECT value FROM system_config WHERE key = 'smtp_host'")
    configured = "true" if host and host.get("value") and has_password else "false"
    db.update(
        "system_config",
        {"value": configured, "updated_at": datetime.now().isoformat()},
        "key = ?",
        ("smtp_configured",),
    )

    flash("Configuracion actualizada", "success")
    return redirect(url_for("settings_ui.settings_ui"))
