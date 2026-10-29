"""Permisos RBAC (ADR-001, MYK-412).

Mapa role->permisos en codigo: versionado en PR, testeable sin BD.
Roles fijos de producto (catalogo cerrado): admin, rrhh, supervisor, auditor.
Todo rol desconocido deniega: has_permission -> False, role_permissions -> vacio.

Diseno y justificacion: docs/adr/ADR-001-rbac-usuarios-perfiles-permisos.md.
La migracion 008_rbac_roles.sql normaliza roles legacy de users.role a este
catalogo; la capa app valida contra ALLOWED_ROLES en todo write path.
"""

from __future__ import annotations

ALLOWED_ROLES = ("admin", "rrhh", "supervisor", "auditor")

# Alias documentado en el ADR-001 ("ROLES").
ROLES = ALLOWED_ROLES

ALL_PERMISSIONS = (
    "devices:read",
    "devices:write",
    "devices:sync",
    "employees:read",
    "employees:write",
    "medical_leaves:read",
    "medical_leaves:write",
    "attendance:read",
    "alerts:read",
    "alerts:write",
    "reports:read",
    "reports:export",
    "users:manage",
    "settings:manage",
    "audit:read",
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset(ALL_PERMISSIONS),
    "rrhh": frozenset(
        {
            "employees:read",
            "employees:write",
            "medical_leaves:read",
            "medical_leaves:write",
            "attendance:read",
            "alerts:read",
            "alerts:write",
            "reports:read",
            "reports:export",
        }
    ),
    "supervisor": frozenset(
        {
            "employees:read",
            "medical_leaves:read",
            "attendance:read",
            "alerts:read",
            "reports:read",
            "reports:export",
        }
    ),
    "auditor": frozenset(
        {
            "employees:read",
            "medical_leaves:read",
            "attendance:read",
            "alerts:read",
            "reports:read",
            "reports:export",
            "audit:read",
        }
    ),
}


def role_permissions(role: str) -> frozenset[str]:
    """Permisos del rol; un rol desconocido no tiene permisos (deny por defecto)."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    """El rol tiene el permiso? Roles desconocidos deniegan todo."""
    return permission in role_permissions(role)
