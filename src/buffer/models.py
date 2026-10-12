"""
Modelos de datos para el buffer SQLite
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AttendanceRecordDB:
    """Modelo de registro de asistencia para base de datos"""

    user_id: str
    timestamp: datetime
    status: int
    device_ip: str
    punch_type: str
    synced: bool = False
    sync_attempts: int = 0

    def to_dict(self) -> dict:
        """Convertir a diccionario"""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat()
            if hasattr(self.timestamp, "isoformat")
            else str(self.timestamp),
            "status": self.status,
            "device_ip": self.device_ip,
            "punch_type": self.punch_type,
            "synced": self.synced,
            "sync_attempts": self.sync_attempts,
        }
