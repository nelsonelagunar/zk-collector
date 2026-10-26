"""
Landing Page Routes - "Attendance Controller" (MYK-409)

Pagina publica de oferta del servicio + formulario de contacto.
Rutas fuera del login (publicas, con o sin sesion):
- GET  /landing          -> landing page de oferta
- POST /landing/contact  -> guarda el lead en `landing_leads` y muestra
                            flash de confirmacion (sin SMTP requerido)
"""

import re
from typing import cast

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..database import Database

landing_bp = Blueprint("landing", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_MAX_LENGTHS = {
    "name": 120,
    "email": 160,
    "company": 160,
    "phone": 40,
    "message": 2000,
}


def _form_value(field: str) -> str:
    value = request.form.get(field, "")
    if not isinstance(value, str):
        return ""
    return value.strip()[: _MAX_LENGTHS[field]]


@landing_bp.route("/landing")
def landing():
    """Landing page publica: renderiza igual con o sin sesion."""
    return render_template("landing.html")


@landing_bp.route("/landing/contact", methods=["POST"])
def contact():
    """Guarda el lead del formulario de contacto y confirma via flash."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    # Honeypot anti-spam (campo oculto que los bots suelen rellenar)
    if request.form.get("website", "").strip():
        flash("¡Gracias! Hemos recibido tu solicitud.", "success")
        return redirect(url_for("landing.landing") + "#contacto")

    name = _form_value("name")
    email = _form_value("email")
    company = _form_value("company")
    phone = _form_value("phone")
    message = _form_value("message")

    if not name or not email or not _EMAIL_RE.match(email):
        flash("Por favor completa tu nombre y un correo válido.", "error")
        return (
            render_template(
                "landing.html",
                form={"name": name, "email": email, "company": company, "message": message},
            ),
            200,
        )

    db.insert(
        "landing_leads",
        {
            "name": name,
            "email": email,
            "company": company or None,
            "phone": phone or None,
            "message": message or None,
        },
    )
    flash("¡Gracias! Hemos recibido tu solicitud y te contactaremos pronto.", "success")
    return redirect(url_for("landing.landing") + "#contacto")
