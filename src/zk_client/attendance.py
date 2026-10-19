"""
Modelo de Registro de Asistencia
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AttendanceRecord:
    """
    Representa un registro de asistencia de dispositivo ZKTeco

    Attributes:
        user_id: ID del usuario
        timestamp: Marca de tiempo del registro
        status: Estado del registro (0=entrada, 1=salida, etc.)
        device_ip: IP del dispositivo que registró
        punch_type: Tipo de marcado (derivado de status)
    """

    user_id: str
    timestamp: datetime
    status: int
    device_ip: str
    punch_type: str = field(init=False)

    def __post_init__(self):
        """Derivar punch_type del status"""
        self.punch_type = self._derive_punch_type()

    def _derive_punch_type(self) -> str:
        """
        Derivar tipo de marcado del status

        ZKTeco status codes:
        0 = Check In (Entrada)
        1 = Check Out (Salida)
        2 = Break Out (Salida a comer)
        3 = Break In (Regreso de comer)
        4 = OT In (Inicio horas extra)
        5 = OT Out (Fin horas extra)
        """
        punch_types = {
            0: "entrada",
            1: "salida",
            2: "salida_comida",
            3: "entrada_comida",
            4: "entrada_extra",
            5: "salida_extra",
        }
        return punch_types.get(self.status, "desconocido")

    @classmethod
    def from_zk_attendance(cls, attendance: Any, device_ip: str) -> "AttendanceRecord":
        """
        Crear AttendanceRecord desde objeto pyzk

        Args:
            attendance: Objeto de asistencia de pyzk
            device_ip: IP del dispositivo

        Returns:
            AttendanceRecord instance
        """
        return cls(
            user_id=str(attendance.user_id),
            timestamp=attendance.timestamp,
            status=attendance.status,
            device_ip=device_ip,
        )

    def to_dict(self) -> dict:
        """Convertir a diccionario"""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "device_ip": self.device_ip,
            "punch_type": self.punch_type,
        }

    def __str__(self) -> str:
        return (
            f"AttendanceRecord(user_id={self.user_id}, "
            f"timestamp={self.timestamp}, "
            f"punch_type={self.punch_type}, "
            f"device={self.device_ip})"
        )
