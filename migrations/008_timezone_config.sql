-- Zona horaria del centro de trabajo (MYK-420, MYK-410 seccion 4 item 2)
-- Huso oficial MX: America/Mexico_City (sin horario de verano desde 2022).
-- Los timestamps naive del firmware se localizan con este huso y todo
-- registro se persiste ISO-8601 con offset; /api/attendance y exports se
-- presentan en la hora local del centro. Valor existente gana (OR IGNORE).

INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('timezone', 'America/Mexico_City', 'IANA timezone of the work center (e.g. America/Mexico_City)');
