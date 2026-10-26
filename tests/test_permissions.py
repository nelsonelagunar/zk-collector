"""Tests del modulo RBAC permissions y la migracion de roles (MYK-412, ADR-001).

- Matriz completa del ADR-001: cada rol x cada permiso -> bool esperado.
- Migracion 008_rbac_roles.sql: normaliza roles legacy (incluido 'user' y
  NULL) a 'auditor' y es re-ejecutable sin error.
"""

import sqlite3
from pathlib import Path

import pytest

from src.webgui.permissions import (
    ALL_PERMISSIONS,
    ALLOWED_ROLES,
    ROLE_PERMISSIONS,
    has_permission,
    role_permissions,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
RBAC_MIGRATION = "008_rbac_roles.sql"

# Matriz exacta del ADR-001 (docs/adr/ADR-001-rbac-usuarios-perfiles-permisos.md).
ADR_MATRIX: dict[str, set[str]] = {
    "admin": {
        "devices:read",
        "devices:write",
        "devices:sync",
        "employees:read",
        "employees:write",
        "medical_leaves:read",
        "medical_leaves:write",
        "attendance:read",
        "reports:read",
        "reports:export",
        "users:manage",
        "settings:manage",
        "audit:read",
    },
    "rrhh": {
        "employees:read",
        "employees:write",
        "medical_leaves:read",
        "medical_leaves:write",
        "attendance:read",
        "reports:read",
        "reports:export",
    },
    "supervisor": {
        "employees:read",
        "medical_leaves:read",
        "attendance:read",
        "reports:read",
        "reports:export",
    },
    "auditor": {
        "employees:read",
        "medical_leaves:read",
        "attendance:read",
        "reports:read",
        "reports:export",
        "audit:read",
    },
}


@pytest.mark.parametrize("permission", ALL_PERMISSIONS)
@pytest.mark.parametrize("role", ALLOWED_ROLES)
def test_has_permission_matches_adr_matrix(role, permission):
    """Cada celda rol x permiso de la matriz del ADR-001 (cobertura 100%)."""
    assert has_permission(role, permission) == (permission in ADR_MATRIX[role])


@pytest.mark.parametrize("role", ALLOWED_ROLES)
def test_role_permissions_matches_adr_matrix(role):
    """role_permissions devuelve exactamente el conjunto del ADR-001."""
    assert role_permissions(role) == frozenset(ADR_MATRIX[role])


def test_allowed_roles_is_the_adr_catalog():
    assert ALLOWED_ROLES == ("admin", "rrhh", "supervisor", "auditor")
    assert set(ROLE_PERMISSIONS) == set(ALLOWED_ROLES)


def test_admin_grants_every_permission():
    assert ROLE_PERMISSIONS["admin"] == frozenset(ALL_PERMISSIONS)


def test_permissions_stay_inside_catalog():
    """Ningun rol concede permisos fuera del catalogo recurso:accion."""
    for role in ALLOWED_ROLES:
        assert role_permissions(role) <= frozenset(ALL_PERMISSIONS)


@pytest.mark.parametrize("permission", ALL_PERMISSIONS)
def test_unknown_role_denies_everything(permission):
    assert has_permission("superuser", permission) is False
    assert has_permission("user", permission) is False
    assert has_permission("", permission) is False


def test_unknown_permission_denied_for_every_role():
    for role in ALLOWED_ROLES:
        assert has_permission(role, "devices:delete") is False


def test_role_permissions_unknown_role_is_empty():
    assert role_permissions("superuser") == frozenset()
    assert role_permissions("user") == frozenset()


# --- Migracion 008_rbac_roles.sql -------------------------------------------


def _connect(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "webgui.db")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply(conn: sqlite3.Connection, *names: str) -> None:
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _insert_user(conn: sqlite3.Connection, username: str, role: str | None) -> None:
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, "hash", role),
    )


def _role_of(conn: sqlite3.Connection, username: str) -> str | None:
    row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return row[0]


def test_migration_normalizes_legacy_roles(tmp_path):
    conn = _connect(tmp_path)
    _apply(conn, "001_initial_schema.sql")

    for username, role in (
        ("root", "admin"),
        ("rosa", "rrhh"),
        ("sup", "supervisor"),
        ("audit", "auditor"),
        ("legado", "user"),
        ("viejo", "superadmin"),
        ("nulo", None),
    ):
        _insert_user(conn, username, role)

    _apply(conn, RBAC_MIGRATION)

    # Roles validos no se tocan; todo lo demas normaliza a 'auditor'.
    assert _role_of(conn, "root") == "admin"
    assert _role_of(conn, "rosa") == "rrhh"
    assert _role_of(conn, "sup") == "supervisor"
    assert _role_of(conn, "audit") == "auditor"
    assert _role_of(conn, "legado") == "auditor"
    assert _role_of(conn, "viejo") == "auditor"
    assert _role_of(conn, "nulo") == "auditor"


def test_migration_is_rerunnable_without_error(tmp_path):
    conn = _connect(tmp_path)
    _apply(conn, "001_initial_schema.sql")
    _insert_user(conn, "legado", "user")

    _apply(conn, RBAC_MIGRATION)
    _apply(conn, RBAC_MIGRATION)  # re-ejecutar no lanza ni cambia nada

    assert _role_of(conn, "legado") == "auditor"
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0] == 0


def test_full_chain_normalizes_demo_seed_roles(webgui_app):
    """La cadena completa (001..008 + demo seed con roles 'user') normaliza a 'auditor'."""
    row = webgui_app.db.fetch_one("SELECT role FROM users WHERE username = 'demo.rrhh'")
    assert row is not None
    assert row["role"] == "auditor"
