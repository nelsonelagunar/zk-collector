"""Tests de integridad del registro de asistencia (MYK-422 / MYK-410 item 4).

Cadena SHA-256 sobre attendance_records, bitacora append-only
(attendance_audit_log), endpoint admin GET /api/attendance/integrity y
correcciones auditadas via POST /api/attendance/records/<id>/correction.
"""

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

from src.buffer.integrity import (
    ATTESTED_FIELDS,
    GENESIS_HASH,
    canonical_payload,
    compute_hash,
    verify_chain,
)
from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.attendance import attendance_bp
from src.webgui.routes.attendance_integrity import attendance_integrity_bp

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
WEBGUI_MIGRATION_CHAIN = ("001_initial_schema.sql", "002_employees.sql")

LEGACY_BUFFER_SCHEMA = """
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        status INTEGER NOT NULL,
        device_ip TEXT NOT NULL,
        punch_type TEXT,
        synced BOOLEAN DEFAULT 0,
        sync_attempts INTEGER DEFAULT 0,
        last_sync_attempt DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_synced ON attendance_records(synced, timestamp);
    CREATE INDEX IF NOT EXISTS idx_timestamp ON attendance_records(timestamp);
    CREATE INDEX IF NOT EXISTS idx_user_id ON attendance_records(user_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance
        ON attendance_records(user_id, timestamp, device_ip);
"""


def _build_app(tmp_path: Path) -> Flask:
    shutil.copytree(MIGRATIONS_DIR, tmp_path / "migrations")
    db_path = tmp_path / "data" / "webgui.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    for name in WEBGUI_MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.buffer_repo = BufferRepository(tmp_path / "data" / "buffer.db")
    app.auth = Auth("test-secret-key")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(attendance_integrity_bp, url_prefix="/api/attendance")
    return app


def _record(
    user_id: str = "101",
    ts: datetime | None = None,
    status: int = 0,
    ip: str = "10.0.0.5",
    punch: str = "entrada",
) -> AttendanceRecordDB:
    return AttendanceRecordDB(
        user_id=user_id,
        timestamp=ts or datetime(2026, 10, 5, 9, 0, 0),
        status=status,
        device_ip=ip,
        punch_type=punch,
    )


def _login(client, role: str = "admin", username: str = "admin.test"):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = username
        sess["role"] = role


@pytest.fixture
def app(tmp_path):
    return _build_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def repo(app):
    return app.buffer_repo


def _fetch_rows(repo: BufferRepository, query: str, params: tuple = ()) -> list[dict]:
    with repo.get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


# ---------------------------------------------------------------------------
# Modulo puro de cadena (src/buffer/integrity.py)
# ---------------------------------------------------------------------------


class TestIntegrityModule:
    def test_canonical_payload_is_stable_and_complete(self):
        row = {
            "user_id": "101",
            "timestamp": "2026-10-05T09:00:00",
            "status": 0,
            "device_ip": "10.0.0.5",
            "punch_type": "entrada",
        }
        payload = canonical_payload(row)
        assert set(json.loads(payload)) == set(ATTESTED_FIELDS)
        # Claves ordenadas: dos llamadas con distinto orden de insercion igualan
        assert payload == canonical_payload(dict(reversed(list(row.items()))))

    def test_compute_hash_matches_manual_sha256(self):
        row = {
            "user_id": "1",
            "timestamp": "2026-10-05T09:00:00",
            "status": 1,
            "device_ip": "10.0.0.5",
            "punch_type": None,
        }
        manual = hashlib.sha256(
            (GENESIS_HASH + canonical_payload(row)).encode("utf-8")
        ).hexdigest()
        assert compute_hash(GENESIS_HASH, row) == manual

    def test_verify_chain_valid_on_well_formed_chain(self):
        rows = []
        prev = GENESIS_HASH
        for i, status in enumerate((0, 1)):
            row = {
                "id": i + 1,
                "user_id": "101",
                "timestamp": f"2026-10-05T0{9 + i}:00:00",
                "status": status,
                "device_ip": "10.0.0.5",
                "punch_type": "entrada",
            }
            row["record_hash"] = compute_hash(prev, row)
            row["prev_hash"] = prev
            prev = row["record_hash"]
            rows.append(row)
        report = verify_chain(rows)
        assert report["valid"] is True
        assert report["records_checked"] == 2
        assert report["failure_count"] == 0

    def test_verify_chain_detects_tampered_content(self):
        row = {
            "id": 1,
            "user_id": "101",
            "timestamp": "2026-10-05T09:00:00",
            "status": 0,
            "device_ip": "10.0.0.5",
            "punch_type": "entrada",
        }
        row["record_hash"] = compute_hash(GENESIS_HASH, row)
        row["prev_hash"] = GENESIS_HASH
        row["timestamp"] = "2026-10-05T08:00:00"  # UPDATE directo
        report = verify_chain([row])
        assert report["valid"] is False
        assert report["failures"][0]["reason"] == "hash_mismatch"
        assert report["first_failure"]["id"] == 1

    def test_verify_chain_empty_and_missing_hash(self):
        assert verify_chain([])["valid"] is True
        report = verify_chain([{"id": 1, "user_id": "1", "record_hash": None, "prev_hash": None}])
        assert report["valid"] is False
        assert report["failures"][0]["reason"] == "missing_hash"


# ---------------------------------------------------------------------------
# BufferRepository: sellado, verificacion, bitacora, correcciones
# ---------------------------------------------------------------------------


class TestBufferChain:
    def test_add_records_seals_chain(self, repo):
        inserted = repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="102", ts=datetime(2026, 10, 5, 9, 1, 0), status=1),
            ]
        )
        assert inserted == 2
        rows = _fetch_rows(repo, "SELECT * FROM attendance_records ORDER BY id ASC")
        assert rows[0]["prev_hash"] == GENESIS_HASH
        assert rows[1]["prev_hash"] == rows[0]["record_hash"]
        assert all(r["record_hash"] for r in rows)
        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["records_checked"] == 2

    def test_direct_update_breaks_chain_and_is_audited(self, repo):
        """AC MYK-422: UPDATE directo -> el verificador lo reporta + bitacora."""
        repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="101", ts=datetime(2026, 10, 5, 17, 0, 0), status=1),
                _record(user_id="102", ts=datetime(2026, 10, 5, 9, 0, 0)),
            ]
        )
        # UPDATE directo (sin pasar por el flujo de correccion)
        with repo.get_connection() as conn:
            conn.execute(
                "UPDATE attendance_records SET timestamp = ? WHERE id = 2",
                ("2026-10-05T16:30:00",),
            )
        report = repo.verify_integrity()
        assert report["valid"] is False
        assert report["first_failure"]["id"] == 2
        assert report["first_failure"]["reason"] == "hash_mismatch"
        audit = _fetch_rows(
            repo, "SELECT * FROM attendance_audit_log WHERE action = 'update'"
        )
        assert len(audit) == 1
        assert audit[0]["actor"] == "trigger"
        assert json.loads(audit[0]["before_values"])["timestamp"] == "2026-10-05T17:00:00"
        assert json.loads(audit[0]["after_values"])["timestamp"] == "2026-10-05T16:30:00"

    def test_delete_breaks_chain_and_is_audited(self, repo):
        repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="102", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="103", ts=datetime(2026, 10, 5, 9, 0, 0)),
            ]
        )
        with repo.get_connection() as conn:
            conn.execute("DELETE FROM attendance_records WHERE id = 2")
        report = repo.verify_integrity()
        assert report["valid"] is False
        assert report["first_failure"]["id"] == 3
        assert report["first_failure"]["reason"] == "prev_hash_mismatch"
        audit = _fetch_rows(
            repo, "SELECT * FROM attendance_audit_log WHERE action = 'delete'"
        )
        assert len(audit) == 1
        assert json.loads(audit[0]["before_values"])["user_id"] == "102"

    def test_sync_state_updates_do_not_break_chain_nor_audit(self, repo):
        """Sync toca estado tecnico: cadena intacta y bitacora sin ruido."""
        repo.add_records([_record()])
        repo.mark_as_synced([1])
        repo.mark_sync_failed([1], max_attempts=5)
        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["audit_entries"] == 0

    def test_correction_via_repo_keeps_chain_and_logs_audit(self, repo):
        """AC MYK-422: correccion deja entrada en bitacora; el original queda anulados."""
        repo.add_records([_record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0))])
        result = repo.correct_record(
            1,
            actor="admin.test",
            reason="solicitud del colaborador",
            timestamp="2026-10-05T09:05:00",
        )
        assert result["original_id"] == 1
        assert result["corrected_id"] == 2
        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["annulled_records"] == 1

        rows = _fetch_rows(repo, "SELECT * FROM attendance_records ORDER BY id ASC")
        assert rows[0]["annulled"] == 1
        assert rows[1]["annulled"] == 0
        assert rows[1]["corrects_record_id"] == 1
        assert rows[1]["timestamp"] == "2026-10-05T09:05:00"

        audit = _fetch_rows(
            repo,
            "SELECT * FROM attendance_audit_log WHERE action IN ('annul', 'correction') "
            "ORDER BY id ASC",
        )
        assert [a["action"] for a in audit] == ["annul", "correction"]
        assert all(a["actor"] == "admin.test" for a in audit)
        assert all(a["reason"] == "solicitud del colaborador" for a in audit)
        before = json.loads(audit[0]["before_values"])
        after = json.loads(audit[1]["after_values"])
        assert before["timestamp"] == "2026-10-05T09:00:00"
        assert after["timestamp"] == "2026-10-05T09:05:00"

    def test_correction_without_reason_or_changes_rejected(self, repo):
        repo.add_records([_record()])
        with pytest.raises(ValueError):
            repo.correct_record(1, actor="a", reason="  ")
        with pytest.raises(ValueError):
            repo.correct_record(1, actor="a", reason="motivo")
        with pytest.raises(KeyError):
            repo.correct_record(99, actor="a", reason="motivo", status=1)

    def test_correction_of_annulled_rejected(self, repo):
        repo.add_records([_record()])
        repo.correct_record(1, actor="a", reason="motivo", status=1)
        with pytest.raises(ValueError):
            repo.correct_record(1, actor="a", reason="otra vez", status=0)

    def test_poll_does_not_resurrect_annulled_record(self, repo):
        """Correccion con la misma clave natural (solo status) + re-poll: sin resurreccion."""
        original = _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0), status=0)
        repo.add_records([original])
        repo.correct_record(1, actor="a", reason="marca invertida", status=1)
        # El reloj vuelve a entregar la misma marcada en el siguiente poll
        assert repo.add_records([original]) == 0
        count = _fetch_rows(repo, "SELECT COUNT(*) AS n FROM attendance_records")[0]["n"]
        assert count == 2
        assert repo.verify_integrity()["valid"] is True

    def test_dedup_keeps_corrected_row_not_annulled_original(self, repo):
        """El dedup de arranque no debe borrar la fila corregida (MIN(id) es el anulado)."""
        repo.add_records([_record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0))])
        repo.correct_record(1, actor="a", reason="estado", status=1)
        # Re-inicializar el repositorio corre el dedup de _init_database
        BufferRepository(repo.db_path, max_records=repo.max_records)
        rows = _fetch_rows(
            repo, "SELECT id, annulled FROM attendance_records ORDER BY id ASC"
        )
        assert [(r["id"], r["annulled"]) for r in rows] == [(1, 1), (2, 0)]
        assert repo.verify_integrity()["valid"] is True

    def test_clear_all_is_audited_and_chain_reset(self, repo):
        repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="102", ts=datetime(2026, 10, 5, 9, 0, 0)),
            ]
        )
        repo.clear_all()
        audit = _fetch_rows(
            repo, "SELECT * FROM attendance_audit_log WHERE action = 'delete'"
        )
        assert len(audit) == 2
        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["records_checked"] == 0

    def test_audit_log_is_append_only(self, repo):
        repo.add_records([_record()])
        # Los guards disparan por fila afectada: sembrar una entrada primero
        with repo.get_connection() as conn:
            conn.execute(
                "INSERT INTO attendance_audit_log (record_id, action, actor, reason) "
                "VALUES (1, 'update', 'seed', 'entrada de prueba')"
            )
        with repo.get_connection() as conn:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute("UPDATE attendance_audit_log SET actor = 'x'")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute("DELETE FROM attendance_audit_log")

    def test_legacy_db_gets_migrated_and_backfilled(self, tmp_path):
        """DB con esquema pre-010: la migracion sella los registros existentes."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        db_path = data_dir / "buffer.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(LEGACY_BUFFER_SCHEMA)
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES ('101', '2026-10-05T09:00:00', 0, '10.0.0.5', 'entrada')"
        )
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES ('102', '2026-10-05T09:02:00', 1, '10.0.0.5', 'salida')"
        )
        conn.commit()
        conn.close()

        (tmp_path / "migrations").mkdir()
        shutil.copytree(
            MIGRATIONS_DIR / "buffer", tmp_path / "migrations" / "buffer"
        )
        repo = BufferRepository(db_path)

        applied = _fetch_rows(repo, "SELECT name FROM _buffer_migrations")
        assert [r["name"] for r in applied] == ["010_attendance_integrity.sql"]
        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["records_checked"] == 2
        backfill_audit = _fetch_rows(
            repo, "SELECT * FROM attendance_audit_log WHERE action = 'chain_backfill'"
        )
        assert len(backfill_audit) == 1

        # Re-init: idempotente, la cadena sigue valida
        BufferRepository(db_path)
        assert repo.verify_integrity()["valid"] is True

    def test_buffer_repo_without_migrations_dir_still_works(self, tmp_path):
        """Layout sin migrations/buffer (ej. tests legacy): el baseline ya trae las columnas."""
        repo = BufferRepository(tmp_path / "test_buffer.db")
        assert repo.add_records([_record()]) == 1
        assert repo.verify_integrity()["valid"] is True

    def test_add_records_coerces_int_user_id(self, repo):
        """Minor review MYK-442: un caller con user_id int no debe sellar mal
        la fila (la columna TEXT la convertiria y el hash quedaria sobre int)."""
        record = AttendanceRecordDB(
            user_id=101,  # type: ignore[arg-type]
            timestamp=datetime(2026, 10, 5, 9, 0, 0),
            status=0,
            device_ip="10.0.0.5",
            punch_type="entrada",
        )
        assert repo.add_records([record]) == 1
        rows = _fetch_rows(repo, "SELECT user_id FROM attendance_records")
        assert rows[0]["user_id"] == "101"
        assert repo.verify_integrity()["valid"] is True


# ---------------------------------------------------------------------------
# Purga automatica vs alteracion (MYK-442 review, hallazgo 2)
# ---------------------------------------------------------------------------


class TestPurgeGapClassification:
    def test_age_purge_leaves_recorded_gap_not_false_alarm(self, repo):
        """H2 review: la purga de sincronizados >30d elimina filas selladas;
        el verificador clasifica el hueco (recorded_purge_gaps) en vez de dar
        falso positivo perpetuo de ALTERACION."""
        old = _record(user_id="101", ts=datetime(2026, 9, 1, 9, 0, 0))
        assert repo.add_records([old]) == 1
        repo.mark_as_synced([1])
        # El siguiente add_records dispara la purga de sincronizados >30d
        assert repo.add_records([_record(user_id="102")]) == 1

        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["failure_count"] == 0
        assert report["purged_records"] == 1
        assert report["recorded_purge_gaps"] == [
            {
                "id": 2,
                "reason": "recorded_purge_gap",
                "detail": "hueco por purga registrada en bitacora (actor='purge')",
                "gap_from": 1,
                "gap_to": 1,
            }
        ]
        purge_audit = _fetch_rows(
            repo, "SELECT * FROM attendance_audit_log WHERE actor = 'purge'"
        )
        assert len(purge_audit) == 1
        assert purge_audit[0]["record_id"] == 1

    def test_capacity_purge_classified_but_direct_delete_still_flags(self, tmp_path):
        """El desborde de capacidad tambien deja hueco clasificado; un DELETE
        directo (sin bitacora actor='purge') sigue siendo posible ALTERACION (AC3)."""
        repo = BufferRepository(tmp_path / "data" / "buffer.db", max_records=2)
        assert (
            repo.add_records(
                [
                    _record(user_id="101", ts=datetime(2026, 10, 5, 8, 0, 0)),
                    _record(user_id="102", ts=datetime(2026, 10, 5, 9, 0, 0)),
                ]
            )
            == 2
        )
        # Desborda: la purga elimina la mas antigua (id 1) y lo deja en bitacora
        assert repo.add_records([_record(user_id="103", ts=datetime(2026, 10, 5, 10, 0, 0))]) == 1

        report = repo.verify_integrity()
        assert report["valid"] is True
        assert report["purged_records"] == 1
        assert report["recorded_purge_gaps"][0]["id"] == 2

        # DELETE directo: la fila siguiente queda en hueco NO registrado
        with repo.get_connection() as conn:
            conn.execute("DELETE FROM attendance_records WHERE id = 2")
        report = repo.verify_integrity()
        assert report["valid"] is False
        assert report["first_failure"]["id"] == 3
        assert report["first_failure"]["reason"] == "prev_hash_mismatch"
        assert report["recorded_purge_gaps"] == []


# ---------------------------------------------------------------------------
# Endpoints admin: /api/attendance/integrity y correcciones
# ---------------------------------------------------------------------------


class TestIntegrityEndpoints:
    def test_integrity_requires_auth(self, client):
        resp = client.get("/api/attendance/integrity")
        assert resp.status_code == 401

    def test_integrity_requires_admin(self, client):
        _login(client, role="user")
        resp = client.get("/api/attendance/integrity")
        assert resp.status_code == 403

    def test_integrity_report_valid_chain(self, client, repo):
        _login(client)
        repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0)),
                _record(user_id="101", ts=datetime(2026, 10, 5, 17, 0, 0), status=1),
            ]
        )
        resp = client.get("/api/attendance/integrity")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["valid"] is True
        assert body["algorithm"] == "sha256"
        assert body["records_checked"] == 2
        assert body["audit_entries"] == 0
        assert "recent_audit" in body and "annulled_records" in body

    def test_integrity_report_detects_tampering(self, client, repo):
        _login(client)
        repo.add_records([_record()])
        with repo.get_connection() as conn:
            conn.execute("UPDATE attendance_records SET user_id = '999' WHERE id = 1")
        resp = client.get("/api/attendance/integrity")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["valid"] is False
        assert body["first_failure"]["reason"] == "hash_mismatch"

    def test_integrity_accepts_bearer_admin_token(self, client, repo):
        repo.add_records([_record()])
        token = client.application.auth.generate_tokens(1, "jwt.admin", "admin")
        resp = client.get(
            "/api/attendance/integrity",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["valid"] is True

    def test_integrity_rejects_non_admin_bearer(self, client):
        token = client.application.auth.generate_tokens(2, "jwt.user", "user")
        resp = client.get(
            "/api/attendance/integrity",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        assert resp.status_code == 403

    def test_correction_via_endpoint_leaves_audit_entry(self, client, repo):
        """AC MYK-422: correccion 'via UI' (sesion admin) deja entrada en bitacora."""
        _login(client, username="admin.test")
        repo.add_records([_record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0))])
        resp = client.post(
            "/api/attendance/records/1/correction",
            json={
                "timestamp": "2026-10-05T09:05:00",
                "status": 1,
                "reason": "reporte del colaborador",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "corrected"
        assert body["audit"] == "recorded"
        assert body["corrected_id"] == 2

        audit = _fetch_rows(
            repo,
            "SELECT * FROM attendance_audit_log WHERE action IN ('annul', 'correction')",
        )
        assert len(audit) == 2
        assert {a["actor"] for a in audit} == {"admin.test"}
        assert repo.verify_integrity()["valid"] is True

        # El listado de la UI muestra la correccion y oculta el original anulado
        listing = client.get("/attendance/api/attendance").get_json()
        timestamps = [r["timestamp"] for r in listing["records"]]
        assert timestamps == ["2026-10-05T09:05:00"]

    def test_correction_validation_errors(self, client, repo):
        _login(client)
        repo.add_records([_record()])
        base = "/api/attendance/records/1/correction"
        assert client.post(base, json={"reason": "sin cambios"}).status_code == 400
        assert client.post(base, json={"status": 1}).status_code == 400
        assert (
            client.post(base, json={"timestamp": "no-fecha", "reason": "x"}).status_code
            == 400
        )
        assert (
            client.post(base, json={"status": "x", "reason": "x"}).status_code == 400
        )
        assert client.post("/api/attendance/records/99/correction",
                           json={"status": 1, "reason": "x"}).status_code == 404

    def test_correction_conflict_with_active_record(self, client, repo):
        _login(client)
        repo.add_records(
            [
                _record(user_id="101", ts=datetime(2026, 10, 5, 9, 0, 0), status=0),
                _record(user_id="101", ts=datetime(2026, 10, 5, 17, 0, 0), status=1),
            ]
        )
        resp = client.post(
            "/api/attendance/records/1/correction",
            json={"timestamp": "2026-10-05T17:00:00", "reason": "x"},
        )
        assert resp.status_code == 409

    def test_correction_requires_admin_session(self, client, repo):
        repo.add_records([_record()])
        resp = client.post(
            "/api/attendance/records/1/correction",
            json={"status": 1, "reason": "x"},
        )
        assert resp.status_code == 401
        _login(client, role="user")
        resp = client.post(
            "/api/attendance/records/1/correction",
            json={"status": 1, "reason": "x"},
        )
        assert resp.status_code == 403
