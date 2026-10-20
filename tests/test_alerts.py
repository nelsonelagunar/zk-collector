"""Tests para el motor de reglas de alertas HR-6 (MYK-227).

- Testes de reglas con fixtures (sin DB real): retardos reincidentes,
  incapacidad por vencer, ausencia sin justificar.
- Testes de rutas API: listar, marcar leida/resuelta, preferencias.
"""

from sqlite3 import Connection
from unittest.mock import Mock

import pytest
from flask import Flask

from src.webgui.alerts import AlertEngine
from src.webgui.database import Database
from src.webgui.routes.alerts import alerts_bp

MIGRATIONS_DIR = None  # se resuelve por test


def _build_app(tmp_path, *migration_names):
    db_path = tmp_path / "webgui.db"
    conn = Connection(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for name in migration_names:
        conn.executescript((migrations_dir() / name).read_text())
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.register_blueprint(alerts_bp, url_prefix="/api/alerts")
    return app


def migrations_dir():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def client(tmp_path):
    app = _build_app(
        tmp_path,
        "001_initial_schema.sql",
        "002_employees.sql",
        "005_alerts.sql",
    )
    # Semilla de datos minima para las FK de alertas
    with app.db.get_connection() as conn:
        conn.execute(
            "INSERT INTO employees (employee_code, first_name, last_name, email) "
            "VALUES ('E001','Ana','Lopez','ana@example.com')"
        )
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role) "
            "VALUES ('admin','admin@example.com','hash','admin')"
        )
        conn.execute(
            "INSERT INTO alert_rules (name, type, enabled, config) "
            "VALUES ('Retardos RH','retardos_reincidentes',1,?)",
            ('{"n": 2, "m_days": 5, "work_start": "09:00"}',),
        )
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-token"
    return client


# ----------------------------------------------------------------------
# Motor de reglas (fixtures, sin DB)
# ----------------------------------------------------------------------


class TestRetardosReincidentes:
    def test_dispara_al_cumplir_n_retardos_en_m_dias(self):
        engine = AlertEngine(Mock())
        records = [
            {"user_id": "E001", "timestamp": "2026-10-16 09:10:00"},
            {"user_id": "E001", "timestamp": "2026-10-17 09:05:00"},
            {"user_id": "E001", "timestamp": "2026-10-18 09:30:00"},
            # entrada temprana (no retardo)
            {"user_id": "E001", "timestamp": "2026-10-19 08:50:00"},
        ]
        alerts = engine.evaluate_retardos_reincidentes(records, n=2, m_days=5)
        assert len(alerts) == 1
        assert alerts[0]["employee_id"] == "E001"
        assert alerts[0]["event_type"] == "retardos_reincidentes"

    def test_no_dispara_por_debajo_de_n(self):
        engine = AlertEngine(Mock())
        records = [
            {"user_id": "E001", "timestamp": "2026-10-16 09:10:00"},
            {"user_id": "E001", "timestamp": "2026-10-17 08:50:00"},
        ]
        alerts = engine.evaluate_retardos_reincidentes(records, n=3, m_days=5)
        assert alerts == []

    def test_no_cuenta_registros_fuera_de_ventana(self):
        engine = AlertEngine(Mock())
        # 2 retardos pero uno fuera de la ventana de 3 dias
        records = [
            {"user_id": "E001", "timestamp": "2026-10-15 09:10:00"},  # fuera (dia 5 si hoy es 20)
            {"user_id": "E001", "timestamp": "2026-10-19 09:10:00"},
        ]
        alerts = engine.evaluate_retardos_reincidentes(records, n=2, m_days=3)
        assert alerts == []


class TestIncapacidadPorVencer:
    def test_dispara_incapacidad_activa_cerca_de_vencer(self):
        engine = AlertEngine(Mock())
        leaves = [
            {"employee_id": 1, "end_date": "2026-10-21", "status": "active"},
            {"employee_id": 2, "end_date": "2026-10-25", "status": "active"},
        ]
        # Today is mocked via date.today(); usamos days_before grande para caer en rango
        alerts = engine.evaluate_incapacidad_por_vencer(leaves, days_before=10)
        ids = {a["employee_id"] for a in alerts}
        assert 1 in ids

    def test_no_dispara_cancelada(self):
        engine = AlertEngine(Mock())
        leaves = [
            {"employee_id": 1, "end_date": "2026-10-21", "status": "cancelled"},
        ]
        alerts = engine.evaluate_incapacidad_por_vencer(leaves, days_before=10)
        assert alerts == []


class TestAusenciaSinJustificar:
    def test_dispara_por_umbral_de_injustificadas(self):
        engine = AlertEngine(Mock())
        absences = [
            {"employee_id": 1, "date": "2026-10-16", "justified": 0},
            {"employee_id": 1, "date": "2026-10-17", "justified": 0},
            {"employee_id": 1, "date": "2026-10-18", "justified": 0},
            {"employee_id": 2, "date": "2026-10-16", "justified": 1},
        ]
        alerts = engine.evaluate_ausencia_sin_justificar(absences, days=2)
        assert len(alerts) == 1
        assert alerts[0]["employee_id"] == 1
        assert alerts[0]["event_type"] == "ausencia_sin_justificar"

    def test_no_cuenta_justificadas(self):
        engine = AlertEngine(Mock())
        absences = [
            {"employee_id": 1, "date": "2026-10-16", "justified": 1},
            {"employee_id": 1, "date": "2026-10-17", "justified": 1},
        ]
        alerts = engine.evaluate_ausencia_sin_justificar(absences, days=2)
        assert alerts == []


# ----------------------------------------------------------------------
# Rutas API
# ----------------------------------------------------------------------


class TestAlertsRoutes:
    def _create_alert(self, app):
        with app.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO alerts (rule_id, employee_id, event_type, message, status) "
                "VALUES (1, 1, 'retardos_reincidentes', '2 retardos en 5 dias', 'pending')"
            )

    def test_list_alerts(self, client):
        app = client.application
        self._create_alert(app)
        resp = client.get("/api/alerts/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["alerts"][0]["status"] == "pending"

    def test_list_alerts_filter_status(self, client):
        app = client.application
        self._create_alert(app)
        resp = client.get("/api/alerts/?status=read")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0

    def test_mark_read(self, client):
        app = client.application
        self._create_alert(app)
        resp = client.patch("/api/alerts/1/read")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "read"
        resp = client.get("/api/alerts/?status=read")
        assert resp.get_json()["total"] == 1

    def test_mark_resolved(self, client):
        app = client.application
        self._create_alert(app)
        resp = client.patch("/api/alerts/1/resolved")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "resolved"

    def test_mark_read_not_found(self, client):
        resp = client.patch("/api/alerts/999/read")
        assert resp.status_code == 404

    def test_preferences(self, client):
        app = client.application
        with app.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO user_alert_preferences (user_id, alert_type, enabled) "
                "VALUES (1, 'retardos_reincidentes', 1)"
            )
        resp = client.get("/api/alerts/preferences?user_id=1")
        assert resp.status_code == 200
        prefs = resp.get_json()["preferences"]
        assert len(prefs) == 1
        assert prefs[0]["alert_type"] == "retardos_reincidentes"

    def test_set_preference(self, client):
        resp = client.post(
            "/api/alerts/preferences",
            json={"user_id": 1, "alert_type": "incapacidad_por_vencer", "enabled": True},
        )
        assert resp.status_code == 201
        assert resp.get_json()["enabled"] is True
