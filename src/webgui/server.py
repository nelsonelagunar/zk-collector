"""
WebGUI Server - Attendance Collector
"""

import contextlib
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, session, url_for

from ..buffer.repository import BufferRepository
from .auth import Auth
from .database import Database


def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("WEBGUI_SECRET_KEY", os.urandom(32).hex())
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    db_path = Path(os.environ.get("DB_PATH", "/opt/attendance/data/webgui.db"))
    app.db = Database(db_path)
    app.db.initialize()

    # BufferRepository para attendance_buffer (SQLite local)
    buffer_db_path = Path(os.environ.get("BUFFER_DB_PATH", "/opt/attendance/data/buffer.db"))
    app.buffer_repo = BufferRepository(buffer_db_path)

    app.auth = Auth(app.config["SECRET_KEY"])

    @app.context_processor
    def utility_processor():
        return {"now": datetime.now}

    from .routes.apidocs import apidocs_bp
    from .routes.attendance import attendance_bp
    from .routes.attendance_stats import attendance_stats_bp
    from .routes.auth import auth_bp
    from .routes.devices import devices_bp
    from .routes.employees import employees_bp
    from .routes.medical_leaves import medical_leaves_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(devices_bp, url_prefix="/devices")
    app.register_blueprint(apidocs_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(attendance_stats_bp, url_prefix="/api/attendance")
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    app.register_blueprint(medical_leaves_bp, url_prefix="/api/medical-leaves")

    @app.route("/")
    def index():
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        stats = {
            "devices_total": len(app.db.fetch_all("SELECT id FROM devices")),
            "devices_online": len(
                app.db.fetch_all("SELECT id FROM devices WHERE status = 'online'")
            ),
            "pending_records": len(
                app.db.fetch_all("SELECT id FROM attendance_buffer WHERE synced = 0")
            ),
        }
        return render_template("dashboard.html", stats=stats)

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "version": "1.0.0"})

    return app


def run_server(host="0.0.0.0", port=8080, debug=False):
    app = create_app()
    app.run(host=host, port=port, debug=debug)


# Instancia a nivel de módulo para WSGI servers (gunicorn src.webgui.server:app)
# Solo crear si no estamos en test (evita errores de FS read-only)
app = None
if os.environ.get("WEBGUI_SKIP_APP_CREATE") != "1":
    with contextlib.suppress(OSError):
        # En entornos sin /opt/attendance writable, no crear la app a nivel de módulo.
        # Se creará explícitamente via create_app() con config apropiada.
        app = create_app()

if __name__ == "__main__":
    run_server(debug=True)
