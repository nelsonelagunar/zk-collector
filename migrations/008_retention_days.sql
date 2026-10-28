-- MYK-419 / RT-1 (MYK-428): retención legal de asistencia (LFT 804-III)
-- retention_days: días mínimos de conservación de registros de asistencia
-- (últimos 26 meses ~= 790 días = último año + 1 año tras la baja + margen;
-- LFT 805: no exhibir = presunción en contra). El borrado del buffer es
-- SOLO manual (purge_synced_older_than) con entrada obligatoria en la
-- bitácora retention_audit.
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('retention_days', '790', 'Minimum days to keep attendance records (LFT 804-III); default 26 meses (~790 días); deletion is manual-only with retention_audit entry');
