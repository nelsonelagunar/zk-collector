"""
Export legal de asistencia (MYK-424, compliance_nomina_2027 seccion 4 item 6).

CSV/XLSX con columnas legales (empleado: codigo/CURP/RFC; razon social con RFC;
centro de trabajo por ubicacion del dispositivo; fecha-hora con zona; tipo de
marca; desglose de jornada LFT 66-68: ordinaria / extra doble / extra triple).

Caso de aceptacion: golden-file con 6 tipos de marca y semana de 11 h extra
(9 dobles + 2 triples).
"""

import csv
import io
import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from flask import Flask
from openpyxl import load_workbook

from src.buffer.repository import BufferRepository
from src.webgui.database import Database
from src.webgui.legal_export import (
    LEGAL_HEADERS,
    build_legal_rows,
    fmt_hours,
    jornada_semana,
    punch_type_name,
)
from src.webgui.routes.attendance import attendance_bp
from src.webgui.routes.auth import auth_bp

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
TZ_MX = ZoneInfo("America/Mexico_City")

WEBGUI_MIGRATIONS = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "008_timezone_config.sql",
    "008_companies.sql",
    "011_employee_labor_data.sql",
)

DEVICE_IP = "10.0.0.5"
DEVICE_SERIAL = "CJXX123456"

PUNCHES = [
    ("101", "2026-10-26T08:00:00-06:00", 0, DEVICE_IP, "entrada"),
    ("101", "2026-10-26T13:00:00-06:00", 2, DEVICE_IP, "salida_comida"),
    ("101", "2026-10-26T13:30:00-06:00", 3, DEVICE_IP, "entrada_comida"),
    ("101", "2026-10-26T19:00:00-06:00", 1, DEVICE_IP, "salida"),
    ("101", "2026-10-27T08:00:00-06:00", 0, DEVICE_IP, "entrada"),
    ("101", "2026-10-27T18:00:00-06:00", 1, DEVICE_IP, "salida"),
    ("101", "2026-10-28T08:00:00-06:00", 0, DEVICE_IP, "entrada"),
    ("101", "2026-10-28T18:00:00-06:00", 1, DEVICE_IP, "salida"),
    ("101", "2026-10-29T08:00:00-06:00", 0, DEVICE_IP, "entrada"),
    ("101", "2026-10-29T17:00:00-06:00", 1, DEVICE_IP, "salida"),
    ("101", "2026-10-30T08:00:00-06:00", 0, DEVICE_IP, "entrada"),
    ("101", "2026-10-30T17:00:00-06:00", 1, DEVICE_IP, "salida"),
    ("101", "2026-10-30T18:00:00-06:00", 4, DEVICE_IP, "entrada_extra"),
    ("101", "2026-10-30T19:00:00-06:00", 5, DEVICE_IP, "salida_extra"),
]


def _apply(conn, *names):
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path, system_timezone="America/Mexico_City"):
    db_path = tmp_path / "data" / "webgui.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _apply(conn, *WEBGUI_MIGRATIONS)
    conn.execute(
        "INSERT OR REPLACE INTO system_config (key, value, description) "
        "VALUES ('timezone', ?, 'huso del centro de trabajo')",
        (system_timezone,),
    )
    conn.execute(
        "INSERT INTO devices (name, location, address, serial_number, is_enabled) "
        "VALUES ('Reloj Planta', 'Planta Norte - Nave 2', '10.0.0.5', 'CJXX123456', 1)"
    )
    conn.execute(
        "INSERT INTO employees (employee_code, first_name, last_name, department, "
        "curp, rfc, status) "
        "VALUES ('EMP-001', 'Ana', 'Torres', 'Produccion', 'TORA850101MDFLNR09', "
        "'TORA850101QZ9', 'active')"
    )
    conn.execute(
        "INSERT INTO employee_device_links (employee_id, device_serial, device_user_id) "
        "VALUES (1, 'CJXX123456', '101')"
    )
    conn.execute(
        "INSERT INTO companies (razon_social, rfc) "
        "VALUES ('Industrias Demo SA de CV', 'IDA060101ABC')"
    )
    conn.execute("INSERT INTO company_devices (company_id, device_serial) VALUES (1, 'CJXX123456')")
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.buffer_repo = BufferRepository(
        tmp_path / "data" / "buffer.db", default_timezone=system_timezone
    )
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    return app


def _login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "auditor.test"
        sess["role"] = "auditor"


def _seed_punches(app, buffer_migration_010=False, annulled_id=None):
    if buffer_migration_010:
        with app.buffer_repo.get_connection() as conn:
            conn.executescript(
                (MIGRATIONS_DIR / "buffer" / "010_attendance_integrity.sql").read_text()
            )
    with app.buffer_repo.get_connection() as conn:
        conn.executemany(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES (?, ?, ?, ?, ?)",
            PUNCHES,
        )
        if annulled_id is not None:
            conn.execute("UPDATE attendance_records SET annulled = 1 WHERE id = ?", (annulled_id,))


def _fetch_records(app):
    with app.buffer_repo.get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM attendance_records ORDER BY id")]


def test_punch_type_todos_los_tipos_de_marca():
    assert [punch_type_name(s) for s in range(6)] == [
        "entrada",
        "salida",
        "salida_comida",
        "entrada_comida",
        "entrada_extra",
        "salida_extra",
    ]
    assert punch_type_name(99) == "desconocido"
    assert punch_type_name(None) == "desconocido"


def test_jornada_11h_extra_semanal_9_dobles_2_triples():
    marcas = {
        date(2026, 10, 26): [
            datetime(2026, 10, 26, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 26, 19, tzinfo=TZ_MX),
        ],
        date(2026, 10, 27): [
            datetime(2026, 10, 27, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 27, 18, tzinfo=TZ_MX),
        ],
        date(2026, 10, 28): [
            datetime(2026, 10, 28, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 28, 18, tzinfo=TZ_MX),
        ],
        date(2026, 10, 29): [
            datetime(2026, 10, 29, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 29, 17, tzinfo=TZ_MX),
        ],
        date(2026, 10, 30): [
            datetime(2026, 10, 30, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 30, 17, tzinfo=TZ_MX),
            datetime(2026, 10, 30, 18, tzinfo=TZ_MX),
            datetime(2026, 10, 30, 19, tzinfo=TZ_MX),
        ],
    }
    ordinaria, dobles, triples = jornada_semana(marcas)
    assert (ordinaria, dobles, triples) == (40.0, 9.0, 2.0)
    assert (fmt_hours(ordinaria), fmt_hours(dobles), fmt_hours(triples)) == (
        "40",
        "9",
        "2",
    )


def test_jornada_sin_extra():
    marcas = {
        date(2026, 10, 26): [
            datetime(2026, 10, 26, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 26, 17, tzinfo=TZ_MX),
        ],
    }
    assert jornada_semana(marcas) == (8.0, 1.0, 0.0)


def test_jornada_dia_una_sola_marca_no_cuenta():
    marcas = {
        date(2026, 10, 26): [datetime(2026, 10, 26, 8, tzinfo=TZ_MX)],
        date(2026, 10, 27): [
            datetime(2026, 10, 27, 8, tzinfo=TZ_MX),
            datetime(2026, 10, 27, 18, tzinfo=TZ_MX),
        ],
    }
    assert jornada_semana(marcas) == (8.0, 2.0, 0.0)


def test_jornada_vacia():
    assert jornada_semana({}) == (0.0, 0.0, 0.0)


def test_golden_csv_legal(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app)

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-30")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.mimetype == "text/csv"
    assert resp.content_type == "text/csv; charset=utf-8"
    assert (
        'filename="asistencia_legal_2026-10-26_2026-10-30.csv"'
        in (resp.headers["Content-Disposition"])
    )

    expected = (REPO_ROOT / "tests" / "fixtures" / "export_legal_golden.csv").read_bytes()
    assert resp.get_data() == expected

    body = resp.get_data(as_text=True)
    assert body.startswith("\ufeff")
    rows = list(csv.reader(io.StringIO(body.removeprefix("\ufeff"))))
    assert rows[0] == LEGAL_HEADERS
    assert len(rows) == 15  # cabecera + 14 marcas
    tipos = {r[8] for r in rows[1:]}
    assert tipos == {
        "entrada",
        "salida",
        "salida_comida",
        "entrada_comida",
        "entrada_extra",
        "salida_extra",
    }
    jornada = {tuple(r[11:]) for r in rows[1:]}
    assert jornada == {("40", "9", "2")}  # 11 h extra: 9 dobles + 2 triples


def test_golden_xlsx_igual_que_csv(tmp_path):
    pytest.importorskip("openpyxl")
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app)

    resp = client.get("/attendance/export?format=xlsx&start_date=2026-10-26&end_date=2026-10-30")
    assert resp.status_code == 200
    assert resp.mimetype == ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    workbook = load_workbook(io.BytesIO(resp.data))
    sheet = workbook.active
    rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    assert rows[0] == LEGAL_HEADERS
    assert len(rows) == 15
    # Estado se guarda entero en el buffer; la fila lo expone como texto.
    assert {r[9] for r in rows[1:]} == {"0", "1", "2", "3", "4", "5"}
    assert {tuple(r[11:]) for r in rows[1:]} == {("40", "9", "2")}


def test_formato_excel_es_alias_de_xlsx(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app)

    resp = client.get("/attendance/export?format=excel")
    assert resp.status_code == 200
    assert resp.mimetype == ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def test_formato_desconocido_400(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    resp = client.get("/attendance/export?format=json")
    assert resp.status_code == 400


def test_fecha_invalida_400(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    resp = client.get("/attendance/export?start_date=not-a-date")
    assert resp.status_code == 400


def test_periodo_sin_registros_devuelve_cabecera_solo(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)

    resp = client.get("/attendance/export?format=csv")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body == "\ufeff" + ",".join(LEGAL_HEADERS) + "\n"


def test_rango_fecha_end_inclusivo(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app)

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-30&end_date=2026-10-30")
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    assert len(rows) == 5  # cabecera + 4 marcas del 30-10


def test_registro_sin_enlace_se_exporta_modo_degradado(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    with app.buffer_repo.get_connection() as conn:
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES ('999', '2026-10-26T09:00:00-06:00', 0, '10.0.0.5', 'entrada')"
        )

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-26")
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    data = rows[1]
    assert data[0] == "" and data[1] == "" and data[2] == "" and data[3] == ""  # sin empleado
    assert data[6] == "Planta Norte - Nave 2"  # centro por ubicacion del dispositivo
    assert data[4] == "Industrias Demo SA de CV"  # razon social llega por dispositivo
    assert data[5] == "IDA060101ABC"
    assert data[8] == "entrada"
    assert data[10] == "2026-W44"


def test_dispositivo_sin_empresa_razon_social_vacia(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    with app.db.get_connection() as conn:
        conn.execute(
            "INSERT INTO devices (name, location, address, serial_number, is_enabled) "
            "VALUES ('Reloj Sin Empresa', 'Bodega 3', '10.0.0.9', 'SN-NOEMP', 1)"
        )
    with app.buffer_repo.get_connection() as conn:
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES ('101', '2026-10-26T09:00:00-06:00', 0, '10.0.0.9', 'entrada')"
        )

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-26")
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    assert rows[1][4] == "" and rows[1][5] == ""  # razon social / RFC patron vacios
    assert rows[1][6] == "Bodega 3"


def test_registros_anulados_no_se_exportan(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app, buffer_migration_010=True, annulled_id=1)

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-26")
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    timestamps = {r[7] for r in rows[1:]}
    assert "2026-10-26T08:00:00-06:00" not in timestamps  # id 1 anulado
    assert len(rows) == 4  # cabecera + las otras 3 marcas del 26-10


def test_export_funciona_sin_columna_annulled(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    _login(client)
    _seed_punches(app)  # buffer sin migration 010: no existe la columna annulled

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-30")
    assert resp.status_code == 200


def test_export_localiza_a_zona_configurada(tmp_path):
    app = _build_app(tmp_path, system_timezone="America/Tijuana")
    client = app.test_client()
    _login(client)
    _seed_punches(app)

    resp = client.get("/attendance/export?format=csv&start_date=2026-10-26&end_date=2026-10-26")
    rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
    assert all(r[7].endswith("-07:00") for r in rows[1:])


def test_export_requiere_sesion(tmp_path):
    app = _build_app(tmp_path)
    client = app.test_client()
    resp = client.get("/attendance/export?format=csv")
    assert resp.status_code == 302


def test_build_legal_rows_desglose_semanal(tmp_path):
    app = _build_app(tmp_path)
    _seed_punches(app)
    records = _fetch_records(app)
    rows = build_legal_rows(records, app.db, app.buffer_repo, TZ_MX)
    assert len(rows) == 14
    assert all(r["Horas ordinarias"] == "40" for r in rows)
    assert all(r["Horas extra dobles"] == "9" for r in rows)
    assert all(r["Horas extra triples"] == "2" for r in rows)
    assert all(r["Semana ISO"] == "2026-W44" for r in rows)
    assert rows[0]["Codigo empleado"] == "EMP-001"
    assert rows[0]["Colaborador"] == "Ana Torres"
    assert rows[0]["CURP"] == "TORA850101MDFLNR09"
    assert rows[0]["RFC"] == "TORA850101QZ9"
    assert rows[0]["Razon social"] == "Industrias Demo SA de CV"
    assert rows[0]["RFC patron"] == "IDA060101ABC"
    assert rows[0]["Centro de trabajo"] == "Planta Norte - Nave 2"
