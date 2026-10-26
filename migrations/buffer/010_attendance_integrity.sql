-- Migration 010 (namespace buffer): integridad del registro de asistencia.
-- MYK-422 / MYK-410 item 4 (IN-1). Target: buffer.db (BufferRepository), NO webgui.db.
--
-- Antecedentes: attendance_records era editable sin rastro (LFT 805 convierte la
-- falta de registro integro en presuncion en contra). Esta migracion anade:
--   * record_hash / prev_hash: cadena SHA-256 por registro (sellado al insertar,
--     verificado por GET /api/attendance/integrity).
--   * annulled / corrects_record_id: correcciones auditadas (anular + insertar),
--     el original nunca se muta: la cadena queda intacta y la bitacora documenta.
--   * attendance_audit_log: append-only (quien/cuando/motivo/antes-despues),
--     poblada por triggers ante UPDATE/DELETE directos y por el flujo de correccion.
--
-- Forward-only. Rollback documentado (requiere respaldo previo, no automatizado):
--   1) DROP TRIGGER trg_attendance_audit_update; trg_attendance_audit_delete;
--      trg_audit_log_no_update; trg_audit_log_no_delete;
--   2) DROP TABLE attendance_audit_log;  (pierde la bitacora: exportar antes)
--   3) Las columnas ADD se dejan (SQLite no soporta DROP COLUMN en todas las
--      versiones soportadas); para retirarlas: recrear attendance_records desde
--      un respaldo seleccionando columnas originales.
--
-- Nota numeracion: el namespace `migrations/buffer/` es independiente del de
-- webgui.db (001-007 en master, 008 en PR de MYK-405); inicia en 010 siguiendo
-- la numeracion del plan de MYK-410 (RT-1 tomara 009 si requiere migracion).

-- 1) Columnas de cadena y correccion (additivas, sin perdida de datos)
ALTER TABLE attendance_records ADD COLUMN record_hash TEXT;
ALTER TABLE attendance_records ADD COLUMN prev_hash TEXT;
ALTER TABLE attendance_records ADD COLUMN annulled BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE attendance_records ADD COLUMN corrects_record_id INTEGER;

-- 2) Bitacora append-only de modificaciones
CREATE TABLE IF NOT EXISTS attendance_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER,
    action TEXT NOT NULL
        CHECK (action IN ('update', 'delete', 'annul', 'correction', 'chain_backfill')),
    actor TEXT NOT NULL,
    reason TEXT,
    before_values TEXT,
    after_values TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON attendance_audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON attendance_audit_log(created_at);

-- 3) Unicidad solo entre registros activos: permite correcciones con la misma
--    clave natural (user_id, timestamp, device_ip) cuando el original queda anulado.
DROP INDEX IF EXISTS idx_unique_attendance;
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance
    ON attendance_records(user_id, timestamp, device_ip)
    WHERE annulled = 0;

-- 4) Triggers de auditoria: cualquier UPDATE que toque los campos atestiguados
--    (user_id, timestamp, status, device_ip, punch_type) fuera del flujo de
--    correccion queda en la bitacora. Los UPDATE de estado tecnico de sync
--    (synced, sync_attempts, updated_at) NO generan ruido de bitacora.
CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_update
AFTER UPDATE ON attendance_records
FOR EACH ROW
WHEN OLD.user_id IS NOT NEW.user_id
  OR OLD.timestamp IS NOT NEW.timestamp
  OR OLD.status IS NOT NEW.status
  OR OLD.device_ip IS NOT NEW.device_ip
  OR OLD.punch_type IS NOT NEW.punch_type
BEGIN
    INSERT INTO attendance_audit_log
        (record_id, action, actor, reason, before_values, after_values)
    VALUES
        (OLD.id, 'update', 'trigger',
         'UPDATE directo: campos atestiguados modificados fuera del flujo de correccion',
         json_object('user_id', OLD.user_id, 'timestamp', OLD.timestamp,
                     'status', OLD.status, 'device_ip', OLD.device_ip,
                     'punch_type', OLD.punch_type),
         json_object('user_id', NEW.user_id, 'timestamp', NEW.timestamp,
                     'status', NEW.status, 'device_ip', NEW.device_ip,
                     'punch_type', NEW.punch_type));
END;

-- Todo DELETE sobre attendance_records queda en la bitacora (incluidas purgas
-- automaticas: evidencia de que el dato existio, LFT 804/805).
CREATE TRIGGER IF NOT EXISTS trg_attendance_audit_delete
AFTER DELETE ON attendance_records
FOR EACH ROW
BEGIN
    INSERT INTO attendance_audit_log
        (record_id, action, actor, reason, before_values)
    VALUES
        (OLD.id, 'delete', 'trigger', 'registro eliminado',
         json_object('user_id', OLD.user_id, 'timestamp', OLD.timestamp,
                     'status', OLD.status, 'device_ip', OLD.device_ip,
                     'punch_type', OLD.punch_type));
END;

-- 5) Inmutabilidad de la bitacora: append-only enforced a nivel DB
CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update
BEFORE UPDATE ON attendance_audit_log
BEGIN
    SELECT RAISE(ABORT, 'attendance_audit_log es append-only (MYK-422)');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete
BEFORE DELETE ON attendance_audit_log
BEGIN
    SELECT RAISE(ABORT, 'attendance_audit_log es append-only (MYK-422)');
END;
