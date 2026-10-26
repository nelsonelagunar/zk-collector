"""
Integridad del registro de asistencia (MYK-422 / MYK-410 item 4)

Cadena de hashes SHA-256 sobre attendance_records (buffer.db):

    record_hash = SHA-256(prev_hash || payload_canonico)

El payload canonico cubre SOLO los campos atestiguados (el contenido que la
autoridad espera intacto): user_id, timestamp, status, device_ip, punch_type.
El estado tecnico (synced, sync_attempts, updated_at, annulled) queda fuera
del hash: marcar sync no rompe la cadena, pero cualquier mutacion de contenido
si. La cadena se recorre por `id` (orden de insercion); el primer registro
cuelga de GENESIS_HASH.

Las correcciones auditadas NO mutan el original: anulan la fila (annulled=1,
fuera del hash) e insertan la fila corregida sellada en la cadena, dejando
entrada en attendance_audit_log. Un UPDATE/DELETE directo rompe la verificacion
y queda capturado por los triggers de bitacora.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

ALGORITHM = "sha256"
GENESIS_HASH = "0" * 64
ATTESTED_FIELDS: tuple[str, ...] = (
    "user_id",
    "timestamp",
    "status",
    "device_ip",
    "punch_type",
)

# Limita el tamano de la respuesta del verificador; failure_count siempre va completo.
MAX_FAILURES_REPORTED = 50


def canonical_payload(record: Mapping[str, Any]) -> str:
    """Serializacion canonica de los campos atestiguados (JSON estable, claves ordenadas)."""
    payload = {name: record.get(name) for name in ATTESTED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(prev_hash: str, record: Mapping[str, Any]) -> str:
    """SHA-256(prev_hash || payload_canonico) en hex."""
    digest = hashlib.sha256((prev_hash + canonical_payload(record)).encode("utf-8"))
    return digest.hexdigest()


def verify_chain(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """
    Verifica la cadena de hashes sobre registros ordenados por id ASC.

    Cada row debe traer: id, los ATTESTED_FIELDS, record_hash y prev_hash.
    Devuelve un reporte:
        valid, algorithm, records_checked, failure_count, failures (<=50),
        first_failure.

    Un fallo en la fila i no arrastrada a i+1: la verificacion sigue la cadena
    ALMACENADA (prev = record_hash guardado), de modo que un UPDATE aislado se
    reporta una sola vez y un DELETE rompe exactamente en el hueco.
    """
    failures: list[dict[str, Any]] = []
    checked = 0
    prev = GENESIS_HASH

    for row in rows:
        checked += 1
        record_hash = row.get("record_hash")
        prev_hash = row.get("prev_hash")

        if record_hash is None or prev_hash is None:
            failures.append(
                {
                    "id": row.get("id"),
                    "reason": "missing_hash",
                    "detail": "registro sin sellar (record_hash/prev_hash NULL)",
                }
            )
            if record_hash:
                prev = record_hash
            continue

        if prev_hash != prev:
            failures.append(
                {
                    "id": row.get("id"),
                    "reason": "prev_hash_mismatch",
                    "expected_prev": prev,
                    "actual_prev": prev_hash,
                }
            )

        expected = compute_hash(prev, row)
        if expected != record_hash:
            failures.append(
                {
                    "id": row.get("id"),
                    "reason": "hash_mismatch",
                    "detail": "contenido no coincide con el hash almacenado (posible ALTERACION)",
                    "expected_hash": expected,
                    "actual_hash": record_hash,
                }
            )

        prev = record_hash

    return {
        "valid": not failures,
        "algorithm": ALGORITHM,
        "records_checked": checked,
        "failure_count": len(failures),
        "failures": failures[:MAX_FAILURES_REPORTED],
        "first_failure": failures[0] if failures else None,
    }
