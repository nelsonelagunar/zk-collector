"""
Excepciones específicas para operaciones ZK
"""


class ZKError(Exception):
    """Excepción base para errores ZK"""
    pass


class ZKConnectionError(ZKError):
    """Error de conexión con dispositivo ZK"""
    pass


class ZKTimeoutError(ZKError):
    """Timeout en operación ZK"""
    pass


class ZKDeviceError(ZKError):
    """Error del dispositivo ZK"""
    pass


class ZKAttendanceError(ZKError):
    """Error obteniendo registros de asistencia"""
    pass


class ZKUserError(ZKError):
    """Error en operaciones de usuarios"""
    pass
