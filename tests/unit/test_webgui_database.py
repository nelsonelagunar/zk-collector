"""
Unit tests for WebGUI Database
"""

import tempfile
from pathlib import Path

import pytest

from src.webgui.database import Database


class TestDatabase:
    """Tests for Database"""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def db(self, temp_db):
        db = Database(temp_db)
        return db

    def test_init_creates_directory(self, temp_db):
        """Test that init creates parent directory"""
        # Directory should be created
        assert temp_db.parent.exists()

    def test_get_connection(self, db):
        """Test get_connection context manager"""
        with db.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_execute(self, db):
        """Test execute query"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        cursor = db.execute("INSERT INTO test (name) VALUES (?)", ("test",))
        assert cursor.lastrowid == 1

        row = db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row is not None
        assert row['name'] == 'test'

    def test_fetch_one(self, db):
        """Test fetch_one"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("one",))
            conn.execute("INSERT INTO test (name) VALUES (?)", ("two",))

        row = db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row is not None
        assert row['name'] == 'one'

        # Non-existent
        row = db.fetch_one("SELECT * FROM test WHERE id = ?", (999,))
        assert row is None

    def test_fetch_all(self, db):
        """Test fetch_all"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("one",))
            conn.execute("INSERT INTO test (name) VALUES (?)", ("two",))

        rows = db.fetch_all("SELECT * FROM test ORDER BY id")
        assert len(rows) == 2
        assert rows[0]['name'] == 'one'
        assert rows[1]['name'] == 'two'

    def test_insert(self, db):
        """Test insert"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")

        id1 = db.insert('test', {'name': 'test1', 'value': 100})
        assert id1 == 1

        id2 = db.insert('test', {'name': 'test2', 'value': 200})
        assert id2 == 2

    def test_update(self, db):
        """Test update"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
            conn.execute("INSERT INTO test (name, value) VALUES (?, ?)", ("old", 10))

        updated = db.update('test', {'name': 'new', 'value': 20}, 'id = ?', (1,))
        assert updated == 1

        row = db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row['name'] == 'new'
        assert row['value'] == 20

    def test_update_no_match(self, db):
        """Test update with no matching rows"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        updated = db.update('test', {'name': 'new'}, 'id = ?', (999,))
        assert updated == 0

    def test_delete(self, db):
        """Test delete"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("to_delete",))

        deleted = db.delete('test', 'id = ?', (1,))
        assert deleted == 1

        row = db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row is None

    def test_delete_no_match(self, db):
        """Test delete with no matching rows"""
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        deleted = db.delete('test', 'id = ?', (999,))
        assert deleted == 0

    def test_initialize_creates_migrations_table(self, db):
        """Test that initialize creates migrations table"""
        db.initialize()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
            )
            table = cursor.fetchone()
            assert table is not None
