"""
Modelo de Registro de Asistencia
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..utils.timezones import coerce_timezone


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
        work_center: Centro de trabajo estampado al capturar (CT-1)
    """

    user_id: str
    timestamp: datetime
    status: int
    device_ip: str
    punch_type: str = field(init=False)
    work_center: str | None = None

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
    def from_zk_attendance(
        cls, attendance: Any, device_ip: str, timezone: Any = None,
        work_center: str | None = None,
    ) -> "AttendanceRecord":
        """
        Crear AttendanceRecord desde objeto pyzk

        Args:
            attendance: Objeto de asistencia de pyzk
            device_ip: IP del dispositivo
            timezone: Huso IANA del dispositivo (MYK-420); el firmware entrega
                datetimes naive (hora de pared del reloj) y se localizan aqui.
            work_center: Centro de trabajo asociado al dispositivo (CT-1).

        Returns:
            AttendanceRecord instance
        """
        timestamp = attendance.timestamp
        if timezone is not None and getattr(timestamp, "tzinfo", None) is None:
            timestamp = timestamp.replace(tzinfo=coerce_timezone(timezone))
        return cls(
            user_id=str(attendance.user_id),
            timestamp=timestamp,
            status=attendance.status,
            device_ip=device_ip,
            work_center=work_center,
        )

    def to_dict(self) -> dict:
        """Convertir a diccionario"""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "device_ip": self.device_ip,
            "punch_type": self.punch_type,
            "work_center": self.work_center,
        }

    def __str__(self) -> str:
        return (
            f"AttendanceRecord(user_id={self.user_id}, "
            f"timestamp={self.timestamp}, "
            f"punch_type={self.punch_type}, "
            f"device={self.device_ip})"
        )
