"""Tests para MedicalLeaveRepository (MYK-239)."""

import shutil
from pathlib import Path

import pytest

from src.webgui.database import Database
from src.webgui.medical_leaves import (
    EmployeeNotFoundError,
    MedicalLeaveRepository,
    ValidationError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_SRC = REPO_ROOT / "migrations"


@pytest.fixture
def db(tmp_path):
    shutil.copytree(MIGRATIONS_SRC, tmp_path / "migrations")
    database = Database(tmp_path / "data" / "webgui.db")
    database.initialize()
    return database


@pytest.fixture
def repo(db):
    return MedicalLeaveRepository(db)


@pytest.fixture
def employee_id(db):
    return db.insert(
        "employees",
        {
            "employee_code": "E001",
            "first_name": "Ana",
            "last_name": "Lopez",
            "department": "RH",
        },
    )


def _payload(employee_id, **extra):
    return {
        "employee_id": employee_id,
        "leave_type": "enfermedad",
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        **extra,
    }


class TestCreate:
    def test_create_ok(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id, doctor_name="Dra. House"))
        assert leave_id > 0
        row = repo.get(leave_id)
        assert row["days"] == 5
        assert row["status"] == "active"

    def test_days_ignored_and_recomputed(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id, days=999))
        row = repo.get(leave_id)
        assert row["days"] == 5

    def test_same_day_counts_one(self, repo, employee_id):
        payload = _payload(employee_id, start_date="2026-02-10", end_date="2026-02-10")
        leave_id = repo.create(payload)
        assert repo.get(leave_id)["days"] == 1

    def test_invalid_leave_type(self, repo, employee_id):
        with pytest.raises(ValidationError):
            repo.create(_payload(employee_id, leave_type="vacaciones"))

    def test_end_date_before_start_date(self, repo, employee_id):
        payload = _payload(employee_id, start_date="2026-01-10", end_date="2026-01-01")
        with pytest.raises(ValidationError):
            repo.create(payload)

    def test_unknown_employee(self, repo):
        with pytest.raises(EmployeeNotFoundError):
            repo.create(_payload(99999))

    def test_document_ref_dict_serialized(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id, document_ref={"bucket": "s3://x"}))
        row = repo.get(leave_id)
        assert row["document_ref"] == '{"bucket": "s3://x"}'


class TestListAndUpdate:
    def test_list_pagination_and_employee_filter(self, repo, db, employee_id):
        other_employee = db.insert("employees", {"employee_code": "E002"})
        for start, end in [("2026-01-01", "2026-01-03"), ("2026-02-01", "2026-02-02")]:
            repo.create(_payload(employee_id, start_date=start, end_date=end))
        repo.create(_payload(other_employee))

        leaves, total = repo.list_leaves(employee_id=employee_id, page=1, per_page=1)
        assert total == 2
        assert len(leaves) == 1

        leaves, total = repo.list_leaves(employee_id=other_employee)
        assert total == 1
        assert leaves[0]["employee_id"] == other_employee

    def test_update_recomputes_days(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id))
        repo.update(leave_id, {"end_date": "2026-01-08", "days": 1})
        row = repo.get(leave_id)
        assert row["days"] == 8

    def test_update_invalid_dates(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id))
        with pytest.raises(ValidationError):
            repo.update(leave_id, {"start_date": "2026-01-10", "end_date": "2026-01-02"})

    def test_cancel_sets_status(self, repo, employee_id):
        leave_id = repo.create(_payload(employee_id))
        assert repo.cancel(leave_id) == 1
        assert repo.get(leave_id)["status"] == "cancelled"


class TestStatsHelper:
    def test_get_leave_dates(self, repo, employee_id):
        repo.create(_payload(employee_id, start_date="2026-03-01", end_date="2026-03-03"))
        repo.create(_payload(employee_id, start_date="2026-03-05", end_date="2026-03-06"))
        dates = repo.get_leave_dates(employee_id, "2026-03-01", "2026-03-31")
        assert dates == ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-05", "2026-03-06"]

    def test_get_leave_dates_excludes_cancelled(self, repo, employee_id):
        leave_id = repo.create(
            _payload(employee_id, start_date="2026-04-01", end_date="2026-04-02")
        )
        repo.cancel(leave_id)
        assert repo.get_leave_dates(employee_id, "2026-04-01", "2026-04-30") == []


class TestVacationOverlap:
    def test_no_table_returns_empty(self, repo, employee_id):
        warnings = repo.vacation_overlap_warnings(employee_id, "2026-01-01", "2026-01-05")
        assert warnings == []

    def test_overlap_with_approved_vacation(self, repo, db, employee_id):
        with db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE vacation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO vacation_requests (employee_id, start_date, end_date, status)
                VALUES (?, ?, ?, 'approved')
                """,
                (employee_id, "2026-01-01", "2026-01-05"),
            )

        warnings = repo.vacation_overlap_warnings(employee_id, "2026-01-03", "2026-01-07")
        assert len(warnings) == 1
        assert "2026-01-01" in warnings[0]

    def test_non_overlapping_vacation_no_warning(self, repo, db, employee_id):
        with db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE vacation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO vacation_requests (employee_id, start_date, end_date, status)
                VALUES (?, ?, ?, 'approved')
                """,
                (employee_id, "2026-02-01", "2026-02-05"),
            )

        warnings = repo.vacation_overlap_warnings(employee_id, "2026-01-01", "2026-01-05")
        assert warnings == []
