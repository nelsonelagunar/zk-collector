"""Tests razon social (companies) + vinculo reloj checador (MYK-405, migration 008)."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.webgui.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_SRC = REPO_ROOT / "migrations"
MIGRATION_008 = MIGRATIONS_SRC / "008_companies.sql"


@pytest.fixture
def db(tmp_path):
    shutil.copytree(MIGRATIONS_SRC, tmp_path / "migrations")
    database = Database(tmp_path / "data" / "webgui.db")
    database.initialize()
    return database


def _read_migration() -> str:
    return MIGRATION_008.read_text()


class TestMigration:
    def test_tables_exist(self, db):
        tables = {
            r["name"] for r in db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"companies", "company_devices"} <= tables

    def test_applied_registered(self, db):
        names = {r["name"] for r in db.fetch_all("SELECT name FROM _migrations")}
        assert "008_companies.sql" in names

    def test_idempotent_rerun(self, db):
        """Re-ejecutar el script 008 directamente no debe fallar (patron migration 002)."""
        conn = sqlite3.connect(str(db.db_path))
        try:
            conn.executescript(_read_migration())  # segunda vez
            conn.executescript(_read_migration())  # tercera vez
        finally:
            conn.close()

    def test_backfill_from_system_config(self, db):
        """Con company_name en system_config y sin empresas, materializa UNA razon social."""
        db.insert(
            "system_config",
            {"key": "company_name", "value": "Fabrica 9to9 S.A. de C.V."},
        )
        conn = sqlite3.connect(str(db.db_path))
        try:
            conn.executescript(_read_migration())
        finally:
            conn.close()
        rows = db.get_companies()
        assert len(rows) == 1
        assert rows[0]["razon_social"] == "Fabrica 9to9 S.A. de C.V."

    def test_backfill_noop_without_company_name(self, db):
        conn = sqlite3.connect(str(db.db_path))
        try:
            conn.executescript(_read_migration())
        finally:
            conn.close()
        assert db.get_companies() == []

    def test_backfill_guards_existing_companies(self, db):
        db.insert("companies", {"razon_social": "Ya Existente S.A."})
        db.insert(
            "system_config",
            {"key": "company_name", "value": "Otra Empresa S.A."},
        )
        conn = sqlite3.connect(str(db.db_path))
        try:
            conn.executescript(_read_migration())
        finally:
            conn.close()
        rows = db.get_companies()
        assert len(rows) == 1
        assert rows[0]["razon_social"] == "Ya Existente S.A."


class TestCompanyCrud:
    def test_create_minimal(self, db):
        company_id = db.create_company({"razon_social": "Comercial XYZ S.A. de C.V."})
        row = db.get_company_by_id(company_id)
        assert row is not None
        assert row["razon_social"] == "Comercial XYZ S.A. de C.V."
        assert row["rfc"] is None
        assert row["imss_registro_patronal"] is None
        assert row["domicilio_fiscal"] is None
        assert row["status"] == "active"

    def test_create_full(self, db):
        company_id = db.create_company(
            {
                "razon_social": "Comercial XYZ S.A. de C.V.",
                "rfc": "CXY040101ABC",
                "imss_registro_patronal": "Y643521810",
                "domicilio_fiscal": "Av. Reforma 100, CDMX",
            }
        )
        row = db.get_company_by_id(company_id)
        assert row["rfc"] == "CXY040101ABC"
        assert row["imss_registro_patronal"] == "Y643521810"
        assert row["domicilio_fiscal"] == "Av. Reforma 100, CDMX"

    def test_get_by_rfc_active_only(self, db):
        company_id = db.create_company({"razon_social": "A", "rfc": "RFC001"})
        assert db.get_company_by_rfc("RFC001") is not None
        db.delete_company(company_id)
        assert db.get_company_by_rfc("RFC001") is None

    def test_rfc_optional_repeated(self, db):
        db.create_company({"razon_social": "A"})
        db.create_company({"razon_social": "B"})
        db.create_company({"razon_social": "C", "rfc": ""})
        db.create_company({"razon_social": "D", "rfc": ""})
        assert len(db.get_companies()) == 4

    def test_rfc_unique_when_present(self, db):
        db.create_company({"razon_social": "A", "rfc": "RFC001"})
        with pytest.raises(sqlite3.IntegrityError):
            db.create_company({"razon_social": "B", "rfc": "RFC001"})

    def test_update(self, db):
        company_id = db.create_company({"razon_social": "Viejo Nombre"})
        db.update_company(company_id, {"razon_social": "Nuevo Nombre", "rfc": "RFC9"})
        row = db.get_company_by_id(company_id)
        assert row["razon_social"] == "Nuevo Nombre"
        assert row["updated_at"] is not None

    def test_delete_is_soft(self, db):
        company_id = db.create_company({"razon_social": "A"})
        assert db.delete_company(company_id) == 1
        row = db.get_company_by_id(company_id)
        assert row["status"] == "inactive"
        assert db.get_companies("active") == []
        assert len(db.get_companies()) == 1

    def test_list_ordered_by_razon_social(self, db):
        db.create_company({"razon_social": "Zeta S.A."})
        db.create_company({"razon_social": "Alfa S.A."})
        assert [r["razon_social"] for r in db.get_companies()] == [
            "Alfa S.A.",
            "Zeta S.A.",
        ]


class TestCompanyDeviceLink:
    def _company(self, db, razon: str) -> int:
        return db.create_company({"razon_social": razon})

    def test_link_and_get_devices(self, db):
        company_id = self._company(db, "Patron A")
        db.link_device_to_company(company_id, "CJXX203260021")
        db.link_device_to_company(company_id, "CJXX203260022")
        devices = db.get_devices_for_company(company_id)
        assert [d["device_serial"] for d in devices] == [
            "CJXX203260021",
            "CJXX203260022",
        ]

    def test_device_belongs_to_one_company(self, db):
        """1:N: re-vincular un reloj a otra empresa transfiere la propiedad."""
        a = self._company(db, "Patron A")
        b = self._company(db, "Patron B")
        db.link_device_to_company(a, "SER-1")
        db.link_device_to_company(b, "SER-1")
        owner = db.get_company_for_device("SER-1")
        assert owner["id"] == b
        assert len(db.get_devices_for_company(a)) == 0
        assert len(db.get_devices_for_company(b)) == 1

    def test_unlink(self, db):
        company_id = self._company(db, "Patron A")
        db.link_device_to_company(company_id, "SER-1")
        assert db.unlink_device_from_company("SER-1") == 1
        assert db.get_company_for_device("SER-1") is None

    def test_get_company_for_device_unknown(self, db):
        assert db.get_company_for_device("NOPE") is None

    def test_join_with_devices_table(self, db):
        db.insert(
            "devices",
            {"name": "Reloj Entrada", "address": "192.168.1.50", "serial_number": "SER-9"},
        )
        company_id = self._company(db, "Patron A")
        db.link_device_to_company(company_id, "SER-9")
        rows = db.get_devices_for_company(company_id)
        assert rows[0]["device_name"] == "Reloj Entrada"
        assert rows[0]["address"] == "192.168.1.50"

    def test_cascade_on_hard_delete(self, db):
        """Esquema declara ON DELETE CASCADE; probado con PRAGMA foreign_keys=ON."""
        company_id = self._company(db, "Patron A")
        db.link_device_to_company(company_id, "SER-1")
        with db.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        assert db.fetch_all("SELECT * FROM company_devices") == []

    def test_link_fk_enforced(self, db):
        with db.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO company_devices (company_id, device_serial) VALUES (?, ?)",
                    (9999, "SER-X"),
                )
