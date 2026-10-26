"""Tests UI de la seccion Razon Social /configuracion/razon-social (MYK-411)."""

API_AUTH = {"Authorization": "Bearer webgui"}


class TestSectionPage:
    def test_anonymous_redirects_to_login(self, webgui_app):
        client = webgui_app.test_client()
        resp = client.get("/configuracion/razon-social")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_logged_renders_inside_layout(self, logged_client):
        _app, client = logged_client
        resp = client.get("/configuracion/razon-social")
        assert resp.status_code == 200
        assert b"Raz\xc3\xb3n Social".decode("utf-8") in resp.get_data(as_text=True)
        assert b"<nav" in resp.data

    def test_route_accepts_both_slash_variants(self, logged_client):
        _app, client = logged_client
        assert client.get("/configuracion/razon-social").status_code == 200
        assert client.get("/configuracion/razon-social/").status_code == 200

    def test_nav_links_section(self, logged_client):
        _app, client = logged_client
        resp = client.get("/settings")
        assert b'href="/configuracion/razon-social"' in resp.data


class TestDevicesSupportEndpoint:
    def test_anonymous_redirects_to_login(self, webgui_app):
        client = webgui_app.test_client()
        resp = client.get("/configuracion/razon-social/api/devices")
        assert resp.status_code == 302

    def test_lists_demo_devices_unlinked(self, logged_client):
        _app, client = logged_client
        resp = client.get("/configuracion/razon-social/api/devices")
        assert resp.status_code == 200
        devices = resp.get_json()["devices"]
        serials = {d["serial_number"] for d in devices}
        assert {"DEMO-SN-0001", "DEMO-SN-0002", "DEMO-SN-0003"} <= serials
        assert all(d["company_id"] is None for d in devices)

    def test_lists_device_with_owner_after_link(self, logged_client):
        _app, client = logged_client
        created = client.post(
            "/api/companies/",
            json={"razon_social": "Planta Norte S.A. de C.V.", "rfc": "PNO260101XXX"},
            headers=API_AUTH,
        )
        assert created.status_code == 201
        company_id = created.get_json()["company"]["id"]

        linked = client.post(
            f"/api/companies/{company_id}/devices",
            json={"device_serial": "DEMO-SN-0001"},
            headers=API_AUTH,
        )
        assert linked.status_code == 201

        devices = client.get("/configuracion/razon-social/api/devices").get_json()["devices"]
        owned = {d["serial_number"]: d for d in devices}["DEMO-SN-0001"]
        assert owned["company_id"] == company_id
        assert owned["razon_social"] == "Planta Norte S.A. de C.V."


class TestUiFlowAgainstApi:
    """El flujo exacto que ejecuta el formulario de companies/index.html."""

    def test_full_crud_and_link_flow(self, logged_client):
        _app, client = logged_client

        created = client.post(
            "/api/companies/",
            json={"razon_social": "Corriente Alterna S.A.", "domicilio_fiscal": "Blvd. Central 5"},
            headers=API_AUTH,
        )
        assert created.status_code == 201
        company = created.get_json()["company"]

        updated = client.put(
            f"/api/companies/{company['id']}",
            json={"imss_registro_patronal": "RP-9988"},
            headers=API_AUTH,
        )
        assert updated.status_code == 200
        assert updated.get_json()["company"]["imss_registro_patronal"] == "RP-9988"

        assert (
            client.post(
                f"/api/companies/{company['id']}/devices",
                json={"device_serial": "DEMO-SN-0002"},
                headers=API_AUTH,
            ).status_code
            == 201
        )

        listed = client.get(f"/api/companies/{company['id']}/devices", headers=API_AUTH).get_json()[
            "devices"
        ]
        assert [d["device_serial"] for d in listed] == ["DEMO-SN-0002"]

        unlinked = client.delete(
            f"/api/companies/{company['id']}/devices/DEMO-SN-0002", headers=API_AUTH
        )
        assert unlinked.status_code == 200

        deleted = client.delete(f"/api/companies/{company['id']}", headers=API_AUTH)
        assert deleted.status_code == 200
        assert (
            client.get(f"/api/companies/{company['id']}", headers=API_AUTH).get_json()["company"][
                "status"
            ]
            == "inactive"
        )
