"""Tests UI de RBAC frontend (MYK-416).

Patron de test_attendance_stats_ui.py / conftest.webgui_app: app real
(create_app) + migraciones + seed demo. AC del issue:
- admin ve menu completo, auditor solo reportes;
- POST en seccion usuarios con rol no-admin devuelve 403;
- pagina 403 amigable + badge de rol en header.
"""

import pytest

STRONG_PASSWORD = "Sup3rSecret!Pass"
ALL_SECTIONS = ("/attendance", "/reportes", "/colaboradores", "/devices", "/users", "/settings")


def _make_user(app, username, role):
    app.db.insert(
        "users",
        {
            "username": username,
            "email": f"{username}@example.com",
            "password_hash": app.auth.hash_password(STRONG_PASSWORD),
            "full_name": username.replace(".", " ").title(),
            "role": role,
            "is_active": 1,
        },
    )


def _login(app, username, role, password=STRONG_PASSWORD):
    _make_user(app, username, role)
    client = app.test_client()
    client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
    return client


def _get_user(app, username):
    return app.db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))


class TestMenuGating:
    def test_admin_sees_menu_completo(self, webgui_app):
        client = _login(webgui_app, "admin.test", "admin")
        body = client.get("/").get_data(as_text=True)
        for href in ALL_SECTIONS:
            assert f'href="{href}"' in body, f"admin no ve {href}"

    def test_auditor_solo_reportes(self, webgui_app):
        client = _login(webgui_app, "auditor.test", "auditor")
        body = client.get("/").get_data(as_text=True)
        assert 'href="/reportes"' in body
        for href in ALL_SECTIONS:
            if href != "/reportes":
                assert f'href="{href}"' not in body, f"auditor no debe ver {href}"

    def test_rrhh_ve_colaboradores_y_reportes(self, webgui_app):
        client = _login(webgui_app, "rrhh.test", "rrhh")
        body = client.get("/").get_data(as_text=True)
        assert 'href="/colaboradores"' in body
        assert 'href="/reportes"' in body
        for href in ("/attendance", "/devices", "/users", "/settings"):
            assert f'href="{href}"' not in body, f"rrhh no debe ver {href}"

    def test_supervisor_ve_reportes_y_asistencia(self, webgui_app):
        client = _login(webgui_app, "supervisor.test", "supervisor")
        body = client.get("/").get_data(as_text=True)
        assert 'href="/reportes"' in body
        assert 'href="/attendance"' in body
        for href in ("/colaboradores", "/devices", "/users", "/settings"):
            assert f'href="{href}"' not in body, f"supervisor no debe ver {href}"

    def test_rol_desconocido_dashboard_only(self, webgui_app):
        # Rol legacy/desconocido: deny por defecto -> solo inicio
        client = _login(webgui_app, "legacy.test", "user")
        body = client.get("/").get_data(as_text=True)
        for href in ALL_SECTIONS:
            assert f'href="{href}"' not in body, f"rol desconocido no debe ver {href}"

    @pytest.mark.parametrize("role", ["rrhh", "supervisor", "auditor"])
    def test_entrada_usuarios_oculta_sin_users_manage(self, webgui_app, role):
        client = _login(webgui_app, f"gate.{role}", role)
        body = client.get("/").get_data(as_text=True)
        assert 'href="/users"' not in body


class TestRoleBadge:
    @pytest.mark.parametrize("role", ["admin", "rrhh", "supervisor", "auditor"])
    def test_badge_de_rol_en_header(self, webgui_app, role):
        client = _login(webgui_app, f"badge.{role}", role)
        body = client.get("/").get_data(as_text=True)
        assert 'id="role-badge"' in body
        assert f'>{role}</span>' in body

    def test_sin_login_no_hay_badge(self, webgui_app):
        body = webgui_app.test_client().get("/auth/login").get_data(as_text=True)
        assert 'id="role-badge"' not in body


class TestUsersManageGating:
    @pytest.mark.parametrize("role", ["rrhh", "supervisor", "auditor"])
    def test_post_users_new_no_admin_devuelve_403(self, webgui_app, role):
        client = _login(webgui_app, f"deny.new.{role}", role)
        resp = client.post(
            "/users/new",
            data={"username": "intruso.pls", "role": "admin", "password": STRONG_PASSWORD},
        )
        assert resp.status_code == 403
        assert _get_user(webgui_app, "intruso.pls") is None

    @pytest.mark.parametrize("role", ["rrhh", "supervisor", "auditor"])
    def test_post_users_edit_no_admin_devuelve_403(self, webgui_app, role):
        target = _get_user(webgui_app, "demo.ventas")
        client = _login(webgui_app, f"deny.edit.{role}", role)
        resp = client.post(
            f"/users/{target['id']}/edit",
            data={"email": "hacked@example.com", "full_name": "H", "role": "admin"},
        )
        assert resp.status_code == 403
        row = _get_user(webgui_app, "demo.ventas")
        assert row["role"] != "admin"

    @pytest.mark.parametrize("role", ["rrhh", "supervisor", "auditor"])
    def test_post_users_toggle_no_admin_devuelve_403(self, webgui_app, role):
        target = _get_user(webgui_app, "demo.ventas")
        client = _login(webgui_app, f"deny.toggle.{role}", role)
        resp = client.post(f"/users/{target['id']}/toggle")
        assert resp.status_code == 403
        assert _get_user(webgui_app, "demo.ventas")["is_active"] == 1

    def test_get_users_no_admin_redirige_a_403_amigable(self, webgui_app):
        client = _login(webgui_app, "get.rrhh", "rrhh")
        resp = client.get("/users")
        assert resp.status_code == 302
        assert "/403" in resp.headers["Location"]
        page = client.get("/users", follow_redirects=True)
        assert page.status_code == 200
        assert "Acceso no autorizado" in page.get_data(as_text=True)

    def test_users_sin_sesion_redirige_a_login(self, webgui_app):
        resp = webgui_app.test_client().get("/users")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


class TestEditUserUi:
    def test_admin_edit_cambia_rol_y_redirige(self, webgui_app):
        client = _login(webgui_app, "editor.admin", "admin")
        target = _get_user(webgui_app, "demo.ventas")
        resp = client.post(
            f"/users/{target['id']}/edit",
            data={"email": "nuevo@example.com", "full_name": "Victor S", "role": "supervisor"},
        )
        assert resp.status_code == 302
        assert "/users" in resp.headers["Location"]
        row = _get_user(webgui_app, "demo.ventas")
        assert row["role"] == "supervisor"
        assert row["email"] == "nuevo@example.com"

    def test_admin_edit_rechaza_rol_fuera_de_catalogo(self, webgui_app):
        client = _login(webgui_app, "badrole.admin", "admin")
        target = _get_user(webgui_app, "demo.ventas")
        resp = client.post(
            f"/users/{target['id']}/edit",
            data={"email": "x@example.com", "full_name": "V", "role": "user"},
        )
        assert resp.status_code == 200
        assert "Rol invalido" in resp.get_data(as_text=True)
        assert _get_user(webgui_app, "demo.ventas")["role"] != "user"

    def test_admin_edit_rechaza_email_duplicado(self, webgui_app):
        client = _login(webgui_app, "dupemail.admin", "admin")
        target = _get_user(webgui_app, "demo.ventas")
        resp = client.post(
            f"/users/{target['id']}/edit",
            data={"email": "demo.admin@demo-corp.com", "full_name": "V", "role": "auditor"},
        )
        assert resp.status_code == 200
        assert "email ya est" in resp.get_data(as_text=True)

    def test_admin_no_degrada_al_ultimo_admin_activo(self, webgui_app):
        client = _login(webgui_app, "solo.admin", "admin")
        demo_admin = _get_user(webgui_app, "demo.admin")
        client.post(f"/users/{demo_admin['id']}/toggle")  # dejar un solo admin activo
        me = _get_user(webgui_app, "solo.admin")
        resp = client.post(
            f"/users/{me['id']}/edit",
            data={"email": "solo@example.com", "full_name": "Solo", "role": "rrhh"},
        )
        assert resp.status_code == 200
        assert "último administrador activo" in resp.get_data(as_text=True)
        assert _get_user(webgui_app, "solo.admin")["role"] == "admin"

    def test_toggle_ultimo_admin_activo_bloqueado(self, webgui_app):
        # Sesion stale: el rol DB del logueado ya no es admin pero su session
        # (emitida al login) sigue dicendolo; demo.admin queda como ultimo
        # admin activo y el guard DB debe impedir desactivarlo.
        client = _login(webgui_app, "guard.admin", "admin")
        webgui_app.db.update("users", {"role": "rrhh"}, "username = ?", ("guard.admin",))
        demo_admin = _get_user(webgui_app, "demo.admin")
        resp = client.post(f"/users/{demo_admin['id']}/toggle", follow_redirects=True)
        body = resp.get_data(as_text=True)
        assert "último administrador activo" in body
        assert _get_user(webgui_app, "demo.admin")["is_active"] == 1

    def test_edit_usuario_inexistente_redirige(self, webgui_app):
        client = _login(webgui_app, "404.admin", "admin")
        resp = client.post("/users/99999/edit", data={"role": "auditor"})
        assert resp.status_code == 302
        assert "/users" in resp.headers["Location"]

    def test_select_de_rol_tiene_los_cuatro_roles(self, webgui_app):
        client = _login(webgui_app, "select.admin", "admin")
        target = _get_user(webgui_app, "demo.ventas")
        new_body = client.get("/users/new").get_data(as_text=True)
        edit_body = client.get(f"/users/{target['id']}/edit").get_data(as_text=True)
        for role in ("admin", "rrhh", "supervisor", "auditor"):
            assert f'value="{role}"' in new_body
            assert f'value="{role}"' in edit_body

    def test_lista_muestra_acciones_editar_y_toggle(self, webgui_app):
        client = _login(webgui_app, "list.admin", "admin")
        target = _get_user(webgui_app, "demo.ventas")
        body = client.get("/users").get_data(as_text=True)
        assert f'href="/users/{target["id"]}/edit"' in body
        assert f'action="/users/{target["id"]}/toggle"' in body


class Test403Page:
    def test_pagina_403_renderiza_amigable(self, webgui_app):
        client = _login(webgui_app, "page.rrhh", "rrhh")
        resp = client.get("/403")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "Acceso no autorizado" in body
        assert "(403)" in body
        assert "rrhh" in body  # badge de rol en contexto

    def test_redirect_de_require_lleva_flash_y_pagina(self, webgui_app):
        # Flujo completo del decorador: GET sin permiso -> 302 a /403 -> 200
        client = _login(webgui_app, "flow.rrhh", "rrhh")
        resp = client.get("/users", follow_redirects=True)
        body = resp.get_data(as_text=True)
        assert "No tienes permiso para administrar usuarios" in body
        assert "Acceso no autorizado" in body
