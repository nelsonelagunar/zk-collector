"""
Database Module - Attendance Collector
Manejo de base de datos SQLite
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """
    Manejo de base de datos SQLite con:
    - Connection pooling básico
    - Migraciones automáticas
    - Context managers para transacciones
    """
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexiones SQLite"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def initialize(self):
        """Inicializar base de datos con migraciones"""
        logger.info(f"Inicializando base de datos: {self.db_path}")
        self._run_migrations()
    
    def _run_migrations(self):
        """Ejecutar migraciones pendientes"""
        migrations_dir = self.db_path.parent.parent / "migrations"
        
        if not migrations_dir.exists():
            logger.warning("Directorio de migraciones no encontrado")
            return
        
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        with self.get_connection() as conn:
            # Crear tabla de migraciones si no existe
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Obtener migraciones aplicadas
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM _migrations")
            applied = {row['name'] for row in cursor.fetchall()}
            
            # Aplicar migraciones pendientes
            for migration_file in migration_files:
                migration_name = migration_file.name
                
                if migration_name in applied:
                    logger.debug(f"Migration {migration_name} ya aplicada")
                    continue
                
                logger.info(f"Aplicando migration: {migration_name}")
                
                with open(migration_file, 'r') as f:
                    sql = f.read()
                
                conn.executescript(sql)
                cursor.execute(
                    "INSERT INTO _migrations (name) VALUES (?)",
                    (migration_name,)
                )
            
            logger.info(f"Migraciones completadas: {len(migration_files)} archivos")
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Ejecutar query simple"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Obtener un registro"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Obtener múltiples registros"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def insert(self, table: str, data: Dict) -> int:
        """Insertar registro"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid
    
    def update(self, table: str, data: Dict, where: str, where_params: tuple = ()) -> int:
        """Actualizar registros"""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        params = tuple(data.values()) + where_params
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
    
    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        """Eliminar registros"""
        query = f"DELETE FROM {table} WHERE {where}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, where_params)
            return cursor.rowcount
