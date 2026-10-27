"""Menu de navegacion por rol (MYK-416, base ADR-001).

Helper unico para templates: la matriz menu<->rol vive aqui (producto), NO se
deriva 1:1 de ROLE_PERMISSIONS. El menu muestra las secciones que el rol USA;
los permisos de ruta (`require()` de MYK-413/414) siguen siendo la autoridad
real de acceso: un rol puede tener un permiso (p.ej. `auditor` tiene
`attendance:read`) sin que la seccion aparezca en su menu.

Roles desconocidos/legacy: solo Dashboard (deny por defecto, consistente con
`permissions.has_permission`).
"""

from __future__ import annotations

from typing import NamedTuple

from flask import session

from .permissions import ALLOWED_ROLES, has_permission


class NavSection(NamedTuple):
    key: str
    label: str
    href: str


SECTIONS: dict[str, NavSection] = {
    "dashboard": NavSection("dashboard", "Dashboard", "/"),
    "attendance": NavSection("attendance", "Asistencia", "/attendance"),
    "reports": NavSection("reports", "Reportes", "/reportes"),
    "employees": NavSection("employees", "Colaboradores", "/colaboradores"),
    "devices": NavSection("devices", "Dispositivos", "/devices"),
    "users": NavSection("users", "Usuarios", "/users"),
    "settings": NavSection("settings", "Configuración", "/settings"),
    "companies": NavSection("companies", "Razón Social", "/configuracion/razon-social"),
}

# Matriz menu por rol (MYK-416): admin ve todo (incluida Razon Social, MYK-411);
# rrhh colaboradores+reportes (incapacidades viven en el expediente del
# colaborador); supervisor reportes+asistencia; auditor solo reportes.
# Dashboard (inicio) para todos.
MENU_BY_ROLE: dict[str, tuple[str, ...]] = {
    "admin": (
        "dashboard",
        "attendance",
        "reports",
        "employees",
        "devices",
        "users",
        "companies",
        "settings",
    ),
    "rrhh": ("dashboard", "employees", "reports"),
    "supervisor": ("dashboard", "reports", "attendance"),
    "auditor": ("dashboard", "reports"),
}

_DASHBOARD_ONLY = ("dashboard",)

# Badge de rol en el header: pares Tailwind 100/800 con contraste WCAG AA.
ROLE_BADGE_CLASSES: dict[str, str] = {
    "admin": "bg-purple-100 text-purple-800",
    "rrhh": "bg-green-100 text-green-800",
    "supervisor": "bg-amber-100 text-amber-800",
    "auditor": "bg-gray-200 text-gray-800",
}
_DEFAULT_BADGE_CLASS = "bg-gray-200 text-gray-800"


def menu_sections_for(role: str) -> tuple[NavSection, ...]:
    """Secciones de menu visibles para el rol; desconocido -> solo Dashboard."""
    keys = MENU_BY_ROLE.get(role, _DASHBOARD_ONLY)
    return tuple(SECTIONS[key] for key in keys if key in SECTIONS)


def role_badge_for(role: str) -> dict[str, str] | None:
    """Badge del rol para el header; sin rol en sesion -> None."""
    if not role:
        return None
    return {"label": role, "class": ROLE_BADGE_CLASSES.get(role, _DEFAULT_BADGE_CLASS)}


def _deny(_perm: str) -> bool:
    return False


def rbac_nav_context() -> dict:
    """Context processor de Flask: expone nav_sections, role_badge y can() a base.html."""
    logged = session.get("user_id") is not None
    role = str(session.get("role", ""))
    can = (lambda perm: has_permission(role, perm)) if logged else _deny
    if not logged:
        return {"nav_sections": (), "role_badge": None, "can": can}
    return {
        "nav_sections": menu_sections_for(role),
        "role_badge": role_badge_for(role),
        "can": can,
    }


__all__ = [
    "ALLOWED_ROLES",
    "MENU_BY_ROLE",
    "NavSection",
    "ROLE_BADGE_CLASSES",
    "SECTIONS",
    "menu_sections_for",
    "rbac_nav_context",
    "role_badge_for",
]
