"""
WebGUI Server - Attendance Collector
"""

import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, session, url_for

from .auth import Auth
from .database import Database
from ..buffer.repository import BufferRepository


def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("WEBGUI_SECRET_KEY", os.urandom(32).hex())
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Ruta única de verdad: WEBGUI_DB_PATH (la misma que usa el entrypoint y
    # el collector). DB_PATH se mantiene solo por retrocompatibilidad.
    default_db_path = os.environ.get("DB_PATH", "/app/data/webgui.db")
    db_path = Path(os.environ.get("WEBGUI_DB_PATH", default_db_path))
    app.db = Database(db_path)
    app.db.initialize()

    # BufferRepository para attendance_buffer (SQLite local)
    buffer_db_path = Path(os.environ.get("BUFFER_DB_PATH", str(db_path.parent / "buffer.db")))
    app.buffer_repo = BufferRepository(buffer_db_path)

    app.auth = Auth(app.config["SECRET_KEY"])
    @app.context_processor
    def utility_processor():
        return {"now": datetime.now}
    from .routes.apidocs import apidocs_bp
    from .routes.auth import auth_bp
    from .routes.devices import devices_bp
    from .routes.attendance import attendance_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(devices_bp, url_prefix="/devices")
    app.register_blueprint(apidocs_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
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
                app.db.fetch_all(
                    "SELECT id FROM attendance_buffer WHERE synced = 0"
                )
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
    try:
        app = create_app()
    except OSError:
        # En entornos sin /opt/attendance writable, no crear la app a nivel de módulo
        # Se creará explícitamente via create_app() con config apropiada
        pass

if __name__ == "__main__":
    run_server(debug=True)
