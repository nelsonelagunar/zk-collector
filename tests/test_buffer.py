"""
Tests para el módulo Buffer
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime

from src.buffer.repository import BufferRepository
from src.buffer.models import AttendanceRecordDB


class TestBufferRepository:
    """Tests para BufferRepository"""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Base de datos temporal para tests"""
        db_path = tmp_path / "test_buffer.db"
        return BufferRepository(db_path, max_records=100)
    
    def test_init(self, temp_db, tmp_path):
        """Test de inicialización"""
        assert temp_db.db_path == tmp_path / "test_buffer.db"
        assert temp_db.max_records == 100
        assert temp_db.db_path.exists()
    
    def test_add_records(self, temp_db):
        """Test de agregar registros"""
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            ),
            AttendanceRecordDB(
                user_id="2",
                timestamp=datetime.now(),
                status=1,
                device_ip="192.168.1.101",
                punch_type="salida"
            )
        ]
        
        count = temp_db.add_records(records)
        
        assert count == 2
    
    def test_get_unsynced_records(self, temp_db):
        """Test de obtención de registros sin sincronizar"""
        # Agregar registro
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
        ]
        temp_db.add_records(records)
        
        # Obtener no sincronizados
        unsynced = temp_db.get_unsynced_records()
        
        assert len(unsynced) == 1
        assert unsynced[0]['user_id'] == "1"
    
    def test_mark_as_synced(self, temp_db):
        """Test de marcar registros como sincronizados"""
        # Agregar registro
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
        ]
        temp_db.add_records(records)
        
        # Obtener ID
        unsynced = temp_db.get_unsynced_records()
        record_id = unsynced[0]['id']
        
        # Marcar como sincronizado
        updated = temp_db.mark_as_synced([record_id])
        
        assert updated == 1
        
        # Verificar
        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 0
    
    def test_get_stats(self, temp_db):
        """Test de obtención de estadísticas"""
        # Agregar algunos registros
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime.now(),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
        ]
        temp_db.add_records(records)
        
        stats = temp_db.get_stats()
        
        assert stats['total_records'] == 1
        assert stats['pending_sync'] == 1
        assert stats['synced'] == 0
    
    def test_cleanup_old_records(self, temp_db):
        """Test de limpieza de registros antiguos"""
        # Agregar registros hasta exceder máximo
        records = []
        for i in range(110):
            records.append(
                AttendanceRecordDB(
                    user_id=str(i),
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                    punch_type="entrada"
                )
            )
        
        temp_db.add_records(records)
        
        stats = temp_db.get_stats()
        assert stats['total_records'] <= temp_db.max_records
    
    def test_log_sync(self, temp_db):
        """Test de log de sincronización"""
        temp_db.log_sync(
            records_synced=10,
            records_failed=0,
            status='success',
            duration_seconds=1.5
        )
        
        history = temp_db.get_sync_history()
        
        assert len(history) == 1
        assert history[0]['records_synced'] == 10
        assert history[0]['status'] == 'success'
