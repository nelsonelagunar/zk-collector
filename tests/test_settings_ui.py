"""Tests de la seccion Configuracion (MYK-377)."""


def test_settings_renders_with_layout_and_company(logged_client):
    _app, client = logged_client
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert b"<nav" in resp.data
    assert b"Empresa Demo S.A. de C.V." in resp.data
    assert b"company_name" in resp.data


def test_settings_requires_session(webgui_app):
    resp = webgui_app.test_client().get("/settings")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_settings_never_shows_smtp_password_value(logged_client):
    app, client = logged_client
    client.post(
        "/settings/update",
        data={"smtp_host": "smtp.demo-corp.com", "smtp_password": "Secret SMTP 123"},
    )
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert b"Secret SMTP 123" not in resp.data
    assert b"Configurada" in resp.data


def test_settings_update_company_name(logged_client):
    app, client = logged_client
    resp = client.post(
        "/settings/update",
        data={"company_name": "Otra Empresa S.A."},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    row = app.db.fetch_one("SELECT value FROM system_config WHERE key = 'company_name'")
    assert row["value"] == "Otra Empresa S.A."


def test_settings_update_requires_admin(user_role_client):
    app, client = user_role_client
    resp = client.post("/settings/update", data={"company_name": "Hack Corp"})
    assert resp.status_code == 302
    row = app.db.fetch_one("SELECT value FROM system_config WHERE key = 'company_name'")
    assert row["value"] == "Empresa Demo S.A. de C.V."


def test_smtp_configured_flag_keeps_existing_password(logged_client):
    """smtp_configured no debe caer a false si el password ya estaba guardado."""
    app, client = logged_client
    client.post(
        "/settings/update",
        data={"smtp_host": "smtp.demo-corp.com", "smtp_password": "Secret SMTP 123"},
    )
    assert (
        app.db.fetch_one("SELECT value FROM system_config WHERE key = 'smtp_configured'")["value"]
        == "true"
    )

    # Segundo update sin re-escribir el password: el flag se conserva
    client.post("/settings/update", data={"smtp_host": "smtp2.demo-corp.com"})
    assert (
        app.db.fetch_one("SELECT value FROM system_config WHERE key = 'smtp_configured'")["value"]
        == "true"
    )
    assert (
        app.db.fetch_one("SELECT value FROM system_config WHERE key = 'smtp_host'")["value"]
        == "smtp2.demo-corp.com"
    )
