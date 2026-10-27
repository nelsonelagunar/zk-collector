"""
Sincronización horaria de relojes ZKTeco (MYK-421, MYK-410 item TZ-1).

El reloj del dispositivo estampa la hora legal de cada marcaje: una deriva
invalida el registro. `src/zk_client/client.py` expone `get_time`/`set_time`
pero el collector no los usaba. En cada poll se compara la hora del
dispositivo contra la del servidor y, si la deriva supera el umbral
(default 60s), se corrige con `set_time()` y se emite alerta por log
(patrón "alerta por log" del buffer, MYK-419).
"""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Umbral por defecto de deriva tolerada, en segundos (MYK-421).
CLOCK_DRIFT_THRESHOLD_SECONDS = 60


@dataclass
class ClockSyncResult:
    """Resultado del chequeo/corrección de reloj de un dispositivo."""

    device_time: datetime
    server_time: datetime
    drift_seconds: float
    threshold_seconds: float
    corrected: bool
    correction_failed: bool = False


def compute_drift_seconds(device_time: object, server_time: datetime) -> float | None:
    """
    Deriva absoluta entre reloj del dispositivo y servidor, en segundos.

    Returns:
        float con la deriva, o None si la hora no es comparable
        (no es datetime o mezcla naive/aware).
    """
    if not isinstance(device_time, datetime) or not isinstance(server_time, datetime):
        return None
    if (device_time.tzinfo is None) != (server_time.tzinfo is None):
        return None
    return abs((device_time - server_time).total_seconds())


def sync_device_clock(
    client,
    *,
    threshold_seconds: float = CLOCK_DRIFT_THRESHOLD_SECONDS,
    server_time: datetime | None = None,
) -> ClockSyncResult | None:
    """
    Comparar get_time() del dispositivo contra la hora del servidor y
    corregir con set_time() si la deriva supera el umbral.

    Args:
        client: ZKClient conectado (o mock con get_time/set_time/ip)
        threshold_seconds: deriva máxima tolerada antes de corregir
        server_time: hora del servidor inyectable para tests; None usa now()

    Returns:
        ClockSyncResult, o None si no se pudo leer/comparar la hora.
    """
    device_time = client.get_time()
    if device_time is None:
        logger.debug(f"{client.ip}: hora del dispositivo no disponible, sync omitida")
        return None

    reference = server_time or datetime.now()
    drift = compute_drift_seconds(device_time, reference)
    if drift is None:
        logger.debug(f"{client.ip}: hora del dispositivo no comparable: {device_time!r}")
        return None

    if drift <= threshold_seconds:
        logger.info(
            f"Reloj {client.ip} sincronizado (deriva {drift:.1f}s <= {threshold_seconds:.0f}s)"
        )
        return ClockSyncResult(
            device_time=device_time,
            server_time=reference,
            drift_seconds=drift,
            threshold_seconds=threshold_seconds,
            corrected=False,
        )

    # Deriva > umbral: corregir con hora fresca del servidor y alertar.
    target = server_time or datetime.now()
    corrected = bool(client.set_time(target))
    if corrected:
        logger.warning(
            "ALERTA drift de reloj %s: deriva %.1fs > umbral %.0fs — corregida "
            "(antes %s, ahora %s)",
            client.ip,
            drift,
            threshold_seconds,
            device_time.isoformat(),
            target.isoformat(),
        )
    else:
        logger.error(
            "ALERTA drift de reloj %s: deriva %.1fs > umbral %.0fs — corrección FALLO",
            client.ip,
            drift,
            threshold_seconds,
        )

    return ClockSyncResult(
        device_time=device_time,
        server_time=reference,
        drift_seconds=drift,
        threshold_seconds=threshold_seconds,
        corrected=corrected,
        correction_failed=not corrected,
    )
