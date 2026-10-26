# Integridad del registro de asistencia (MYK-422 / MYK-410 item 4)

Cadena de hashes SHA-256 + bitácora inmutable sobre `attendance_records` (buffer.db),
para que un registro de jornada sea defendible ante STPS/junta (LFT 805: la falta de
registro íntegro es presunción en contra). Implementación: `src/buffer/integrity.py`,
`src/buffer/repository.py`, `migrations/buffer/010_attendance_integrity.sql`,
`src/webgui/routes/attendance_integrity.py`.

## Modelo

### Cadena de hashes

```
record_hash = SHA-256(prev_hash || payload_canonico)
payload_canonico = JSON estable de {user_id, timestamp, status, device_ip, punch_type}
prev_hash = record_hash del registro anterior (por id); génesis = 64 ceros
```

- El hash cubre SOLO los campos **atestiguados** (el contenido probatorio). El estado
  técnico de sync (`synced`, `sync_attempts`, `updated_at`) y el estado de corrección
  (`annulled`) quedan fuera: marcar sync no rompe la cadena.
- Se sella al insertar (`BufferRepository.add_records`) y se verifica con
  `GET /api/attendance/integrity` (admin). `prev_hash_mismatch` señala el hueco de un
  DELETE; `hash_mismatch` señala un UPDATE de contenido.
- **Backfill**: los registros pre-migración se sellan al aplicar `migrations/buffer/010`
  (entrada `chain_backfill` en la bitácora). La migración es forward-only; el rollback
  va documentado en el propio archivo SQL.
- Las futuras columnas atestiguadas (p.ej. `utc_timestamp` de MYK-410 item 2) deberán
  extender `ATTESTED_FIELDS` y re-sellar con migración propia.

### Bitácora append-only (`attendance_audit_log`)

- Columnas: `record_id`, `action` (update/delete/annul/correction/chain_backfill),
  `actor`, `reason`, `before_values`, `after_values`, `created_at`.
- Poblada por **triggers** de SQLite: cualquier UPDATE que toque campos atestiguados
  y cualquier DELETE (incluidas purgas automáticas — evidencia de que el dato existió).
  Los UPDATE de solo-sync no generan ruido.
- Inmutabilidad forzada a nivel BD: triggers `BEFORE UPDATE/DELETE` con
  `RAISE(ABORT, 'attendance_audit_log es append-only')`.

### Correcciones auditadas

Un UPDATE de contenido rompería la cadena, así que la corrección NUNCA muta:

1. El original queda `annulled=1` (fuera del hash; contenido preservado).
2. Se inserta la fila corregida, sellada en la cadena (`corrects_record_id` apunta al original).
3. La bitácora recibe `annul` + `correction` con quién/motivo/anterior-posterior.

El índice único es **parcial** (`WHERE annulled = 0`): una corrección puede conservar la
clave natural (user_id+timestamp+device_ip) sin colisionar con su original. El dedup de
polling además consulta también anulados: un re-poll no resucita marcadas anuladas.
Listados, exportaciones y stats excluyen registros anulados; la bitácora es el historial.

## Endpoints (admin: sesión WebGUI o Bearer JWT role=admin)

- `GET /api/attendance/integrity` — reporte: `valid`, `algorithm`, `records_checked`,
  `failure_count`, `failures` (≤50), `first_failure`, `audit_entries`, `recent_audit` (10),
  `annulled_records`, `purged_records`, `recorded_purge_gaps`. Devuelve 200 aunque la
  cadena esté rota: el veredicto va en `valid`.
- `POST /api/attendance/records/{id}/correction` — body JSON con al menos un campo
  corregible (`timestamp` ISO-8601, `status`, `punch_type`, `device_ip`) + `reason`
  obligatorio. Respuesta 200 con `corrected_id`; 409 si ya está anulado o colisiona con
  un registro activo.

La UI de `/attendance` (solo admin) muestra la columna **Acciones** con el modal de
corrección; el `reason` es obligatorio en el formulario.

## Criterios de aceptación verificados (tests en `tests/test_attendance_integrity.py`)

1. **UPDATE directo → verificador lo reporta**: test cambia un `timestamp` con SQL crudo;
   `/api/attendance/integrity` responde `valid=false`, `first_failure.reason=hash_mismatch`,
   y el trigger deja la entrada `update` en la bitácora.
2. **Corrección vía UI → bitácora**: POST de corrección con sesión admin deja entradas
   `annul`+`correction` con actor y motivo; la cadena sigue `valid=true`.
3. DELETE directo → `prev_hash_mismatch` + entrada `delete` en bitácora.
4. Sync no rompe cadena ni llena bitácora; polling idempotente no resucita anulados;
   DB legada se migra y sella; bitácora append-only (UPDATE/DELETE → IntegrityError).

## Limitaciones conocidas

- El head de la cadena no está anclado externamente (firma/sello externo queda como
  trabajo futuro de MYK-410): un atacante con acceso SQL completo podría re-sellar;
  la bitácora append-only y los triggers de auditoría siguen dejando rastro de que
  hubo UPDATE/DELETE.
- La purga automática del buffer (`_cleanup_old_records`: sincronizados >30 días y
  desborde de capacidad) elimina filas **selladas** y deja huecos permanentes en la
  cadena. Para que el verificador no dé falso positivo perpetuo, cada id purgado se
  registra en bitácora con `actor='purge'` **antes** de borrarlo y `verify_integrity`
  clasifica esos huecos aparte (`recorded_purge_gaps`, `purged_records`) sin invalidar
  `valid`. Un DELETE fuera de la purga solo deja la entrada del trigger
  (`actor='trigger'`) y sigue reportándose como posible ALTERACIÓN (AC 3). Residual:
  no se puede distinguir una alteración de la fila inmediatamente posterior a un hueco
  de purga (el fallo hereda la clasificación del hueco). MYK-419 (retención legal ≥730d)
  elimina de raíz el borrado automático.
- La anulación no se propaga al sync cloud (la fila corregida se sincroniza como nueva).
- `clear_all` (operación manual) elimina registros; cada DELETE queda en bitácora.
