-- MYK-419: retención legal de asistencia (LFT 804-III)
-- retention_days: días mínimos de conservación de registros de asistencia
-- (último año + 1 año tras baja => 730 días; LFT 805: no exhibir = presunción
-- en contra). El borrado del buffer es SOLO manual (purge_synced_older_than)
-- con entrada obligatoria en la bitácora retention_audit.
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('retention_days', '730', 'Minimum days to keep attendance records (LFT 804-III); deletion is manual-only with retention_audit entry');
