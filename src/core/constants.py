"""
Constantes globales del sistema
"""

# Versión
VERSION = "1.0.0"

# Timeout por defecto (segundos)
DEFAULT_TIMEOUT = 30
ZK_DEFAULT_TIMEOUT = 5
ZK_DEFAULT_PORT = 4370

# Intervalos (segundos)
DEFAULT_POLL_INTERVAL = 300  # 5 minutos
DEFAULT_SYNC_INTERVAL = 60   # 1 minuto
DEFAULT_HEARTBEAT_INTERVAL = 300  # 5 minutos
DEFAULT_UPDATE_CHECK_INTERVAL = 86400  # 24 horas

# Buffer
DEFAULT_MAX_RECORDS = 10000
DEFAULT_CLEANUP_DAYS = 30

# Reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2.0
SYNC_MAX_RETRIES = 5

# Logging
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "text"  # text or json
DEFAULT_LOG_MAX_SIZE_MB = 10
DEFAULT_LOG_BACKUP_COUNT = 5

# Rutas por defecto
DEFAULT_CONFIG_PATH = "/etc/attendance/collector.yaml"
DEFAULT_DATA_DIR = "/opt/attendance/data"
DEFAULT_LOG_DIR = "/var/log/attendance"
DEFAULT_APP_DIR = "/opt/attendance"

# Seguridad
ENCRYPTION_ALGORITHM = "AES-256"

# HTTP
HTTP_TIMEOUT = 30
HTTP_RETRY_ATTEMPTS = 3
