"""Tests para las rutas CRUD /api/companies (MYK-411)."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.companies import companies_bp

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_SRC = REPO_ROOT / "migrations"

SECRET = "test-secret-key"
AUTH_HEADER = {
    "Authorization": (
        f"Bearer {Auth(SECRET).generate_tokens(1, 'admin', 'admin')['access_token']}"
    )
}


def _build_app(tmp_path: Path) -> Flask:
    shutil.copytree(MIGRATIONS_SRC, tmp_path / "migrations")
    db_path = tmp_path / "data" / "webgui.db"
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.db.initialize()
    app.auth = Auth(app.config["SECRET_KEY"])
    app.register_blueprint(companies_bp, url_prefix="/api/companies")
    return app


@pytest.fixture
def client(tmp_path: Path):
    app = _build_app(tmp_path)
    return app.test_client()


@pytest.fixture
def device_serial(client):
    """Reloj con serial para pruebas de vinculo (patron devices seed demo)."""
    client.application.db.insert(
        "devices",
        {
            "name": "Reloj Test",
            "address": "192.168.1.101",
            "serial_number": "SN-001",
            "is_enabled": 1,
        },
    )
    return "SN-001"


def _create(client, **extra):
    payload = {"razon_social": "Fabrica 9to9 S.A. de C.V.", **extra}
    return client.post("/api/companies/", json=payload, headers=AUTH_HEADER)


def _create_id(client, **extra):
    resp = _create(client, **extra)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["company"]["id"]


class TestAuth:
    def test_requires_authorization_header(self, client):
        resp = client.get("/api/companies/")
        assert resp.status_code == 401

    def test_accepts_bearer_token(self, client):
        resp = client.get("/api/companies/", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json() == {"companies": []}


class TestCreate:
    def test_create_returns_201_with_company(self, client):
        resp = _create(client, rfc="FAB990101ABC", domicilio_fiscal="Av. Principal 1")
        assert resp.status_code == 201
        company = resp.get_json()["company"]
        assert company["razon_social"] == "Fabrica 9to9 S.A. de C.V."
        assert company["rfc"] == "FAB990101ABC"
        assert company["status"] == "active"
        assert company["id"] is not None

    def test_create_without_razon_social_is_400(self, client):
        resp = client.post("/api/companies/", json={"rfc": "X"}, headers=AUTH_HEADER)
        assert resp.status_code == 400
        assert "razon_social" in resp.get_json()["error"]

    def test_create_empty_razon_social_is_400(self, client):
        resp = client.post("/api/companies/", json={"razon_social": "  "}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_create_duplicate_rfc_is_409(self, client):
        assert _create(client, rfc="DUP123").status_code == 201
        resp = _create(client, rfc="DUP123")
        assert resp.status_code == 409

    def test_create_blank_rfc_twice_is_ok(self, client):
        """RFC vacio/None no choca: indice UNIQUE parcial (docs/companies.md)."""
        assert _create(client, rfc="").status_code == 201
        assert _create(client).status_code == 201

    def test_create_non_dict_body_is_400(self, client):
        resp = client.post("/api/companies/", json=["no", "dict"], headers=AUTH_HEADER)
        assert resp.status_code == 400
        assert "body JSON requerido" in resp.get_json()["error"]


class TestGet:
    def test_get_existing(self, client):
        company_id = _create_id(client)
        resp = client.get(f"/api/companies/{company_id}", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()["company"]["id"] == company_id

    def test_get_missing_is_404(self, client):
        resp = client.get("/api/companies/999", headers=AUTH_HEADER)
        assert resp.status_code == 404


class TestUpdate:
    def test_update_partial(self, client):
        company_id = _create_id(client, domicilio_fiscal="Calle Vieja 10")
        resp = client.put(
            f"/api/companies/{company_id}",
            json={"domicilio_fiscal": "Calle Nueva 20"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        company = resp.get_json()["company"]
        assert company["domicilio_fiscal"] == "Calle Nueva 20"
        assert company["razon_social"] == "Fabrica 9to9 S.A. de C.V."

    def test_update_razon_social_empty_is_400(self, client):
        company_id = _create_id(client)
        resp = client.put(
            f"/api/companies/{company_id}", json={"razon_social": ""}, headers=AUTH_HEADER
        )
        assert resp.status_code == 400

    def test_update_no_fields_is_400(self, client):
        company_id = _create_id(client)
        resp = client.put(f"/api/companies/{company_id}", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_update_missing_is_404(self, client):
        resp = client.put("/api/companies/999", json={"rfc": "A"}, headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_update_duplicate_rfc_is_409(self, client):
        _create_id(client, rfc="RFC-AAA")
        other = _create_id(client, rfc="RFC-BBB")
        resp = client.put(f"/api/companies/{other}", json={"rfc": "RFC-AAA"}, headers=AUTH_HEADER)
        assert resp.status_code == 409


class TestDelete:
    def test_delete_is_soft(self, client):
        company_id = _create_id(client)
        resp = client.delete(f"/api/companies/{company_id}", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        row = client.get(f"/api/companies/{company_id}", headers=AUTH_HEADER).get_json()["company"]
        assert row["status"] == "inactive"

        active = client.get("/api/companies/?status=active", headers=AUTH_HEADER).get_json()[
            "companies"
        ]
        assert all(c["id"] != company_id for c in active)

    def test_delete_missing_is_404(self, client):
        resp = client.delete("/api/companies/999", headers=AUTH_HEADER)
        assert resp.status_code == 404


class TestDeviceLinks:
    def test_link_device(self, client, device_serial):
        company_id = _create_id(client)
        resp = client.post(
            f"/api/companies/{company_id}/devices",
            json={"device_serial": device_serial},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 201
        assert resp.get_json()["link"] == {"company_id": company_id, "device_serial": device_serial}

        devices = client.get(
            f"/api/companies/{company_id}/devices", headers=AUTH_HEADER
        ).get_json()["devices"]
        assert [d["device_serial"] for d in devices] == [device_serial]
        assert devices[0]["device_name"] == "Reloj Test"

    def test_link_requires_device_serial(self, client):
        company_id = _create_id(client)
        resp = client.post(f"/api/companies/{company_id}/devices", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_link_unknown_serial_is_404(self, client):
        company_id = _create_id(client)
        resp = client.post(
            f"/api/companies/{company_id}/devices",
            json={"device_serial": "NOPE-404"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    def test_link_missing_company_is_404(self, client, device_serial):
        resp = client.post(
            "/api/companies/999/devices",
            json={"device_serial": device_serial},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    def test_relink_transfers_ownership(self, client, device_serial):
        """1:N con UNIQUE(device_serial): re-ligar transfiere el reloj a la nueva razon social."""
        first = _create_id(client, razon_social="Empresa Uno S.A.")
        second = _create_id(client, razon_social="Empresa Dos S.A.")

        assert (
            client.post(
                f"/api/companies/{first}/devices",
                json={"device_serial": device_serial},
                headers=AUTH_HEADER,
            ).status_code
            == 201
        )
        resp = client.post(
            f"/api/companies/{second}/devices",
            json={"device_serial": device_serial},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 201

        owner = client.application.db.get_company_for_device(device_serial)
        assert owner["id"] == second

        first_devices = client.get(
            f"/api/companies/{first}/devices", headers=AUTH_HEADER
        ).get_json()["devices"]
        assert first_devices == []

    def test_unlink_device(self, client, device_serial):
        company_id = _create_id(client)
        client.post(
            f"/api/companies/{company_id}/devices",
            json={"device_serial": device_serial},
            headers=AUTH_HEADER,
        )

        resp = client.delete(
            f"/api/companies/{company_id}/devices/{device_serial}", headers=AUTH_HEADER
        )
        assert resp.status_code == 200

        devices = client.get(
            f"/api/companies/{company_id}/devices", headers=AUTH_HEADER
        ).get_json()["devices"]
        assert devices == []

    def test_list_devices_missing_company_is_404(self, client):
        resp = client.get("/api/companies/999/devices", headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_unlink_missing_company_is_404(self, client, device_serial):
        resp = client.delete(f"/api/companies/999/devices/{device_serial}", headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_unlink_not_linked_is_404(self, client, device_serial):
        company_id = _create_id(client)
        resp = client.delete(
            f"/api/companies/{company_id}/devices/{device_serial}", headers=AUTH_HEADER
        )
        assert resp.status_code == 404

    def test_unlink_other_company_device_is_404(self, client, device_serial):
        """Desligar un reloj que pertenece a OTRA empresa no debe desligarlo."""
        first = _create_id(client, razon_social="Empresa Uno S.A.")
        second = _create_id(client, razon_social="Empresa Dos S.A.")
        client.post(
            f"/api/companies/{first}/devices",
            json={"device_serial": device_serial},
            headers=AUTH_HEADER,
        )

        resp = client.delete(
            f"/api/companies/{second}/devices/{device_serial}", headers=AUTH_HEADER
        )
        assert resp.status_code == 404

        owner = client.application.db.get_company_for_device(device_serial)
        assert owner["id"] == first


class TestMigrationContract:
    def test_routes_run_over_migration_008_tables(self, client):
        """La API opera sobre tablas de migration 008 en DB inicializada solo con migrations/."""
        conn = sqlite3.connect(str(client.application.db.db_path))
        try:
            tables = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        finally:
            conn.close()
        assert {"companies", "company_devices"} <= tables
