"""
Zonas horarias para registros de asistencia (MYK-420)

El firmware ZKTeco entrega datetimes naive (hora de pared del reloj). Para que
un registro sea demostrable frente a la LFT (art. 804) debe quedar persistido
en ISO-8601 con offset y presentarse en la hora local del centro de trabajo
(`system_config.timezone`, default America/Mexico_City).
"""

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "America/Mexico_City"

_LEGACY_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def coerce_timezone(value: Any = None) -> ZoneInfo:
    """Convierte str|ZoneInfo|None a ZoneInfo con fallback al huso default."""
    if isinstance(value, ZoneInfo):
        return value
    if value:
        try:
            return ZoneInfo(str(value).strip())
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo(DEFAULT_TIMEZONE)


def get_system_timezone(db: Any = None) -> str:
    """
    Huso del centro de trabajo: system_config.timezone (webgui.db) -> env
    ZK_TIMEZONE -> DEFAULT_TIMEZONE. Nunca lanza: valor invalido cae al default.
    """
    if db is not None:
        try:
            row = db.fetch_one("SELECT value FROM system_config WHERE key = 'timezone'")
        except Exception:
            row = None
        if row and row.get("value"):
            return str(row["value"]).strip()
    env = os.environ.get("ZK_TIMEZONE", "").strip()
    return env or DEFAULT_TIMEZONE


def parse_timestamp(value: Any) -> datetime | None:
    """
    Parsea timestamps del buffer: ISO-8601 (con o sin offset, con 'T' o espacio)
    y formatos legacy 'YYYY-MM-DD[ HH:MM[:SS]]'. Devuelve None si no parsea.
    """
    if isinstance(value, datetime):
        return value
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in _LEGACY_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def ensure_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    """Asigna tz a un datetime naive (hora de pared del dispositivo)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def to_local(value: Any, tz: ZoneInfo) -> datetime | None:
    """Parsea y convierte a la zona local; un naive se asume en tz."""
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return ensure_aware(parsed, tz).astimezone(tz)


def to_local_iso(value: Any, tz: ZoneInfo) -> str:
    """Representacion ISO-8601 con offset en la zona local del centro."""
    local = to_local(value, tz)
    if local is None:
        return str(value)
    return local.isoformat()
