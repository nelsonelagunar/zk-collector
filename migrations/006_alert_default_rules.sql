-- HR-6: Reglas de alerta por defecto (MYK-227)
-- Idempotente: solo inserta si no existe una regla del mismo tipo.

INSERT INTO alert_rules (name, type, enabled, config)
SELECT 'Retardos reincidentes', 'retardos_reincidentes', 1, '{"n": 3, "m_days": 5}'
WHERE NOT EXISTS (SELECT 1 FROM alert_rules WHERE type = 'retardos_reincidentes');

INSERT INTO alert_rules (name, type, enabled, config)
SELECT 'Incapacidad por vencer', 'incapacidad_por_vencer', 1, '{"days_before": 3}'
WHERE NOT EXISTS (SELECT 1 FROM alert_rules WHERE type = 'incapacidad_por_vencer');

INSERT INTO alert_rules (name, type, enabled, config)
SELECT 'Ausencia sin justificar', 'ausencia_sin_justificar', 1, '{"days": 3}'
WHERE NOT EXISTS (SELECT 1 FROM alert_rules WHERE type = 'ausencia_sin_justificar');
