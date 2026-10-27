-- 009: Portal del trabajador /mi-asistencia (MYK-425, MYK-410 item 7)
-- Credencial propia del trabajador: PIN por empleado (Argon2id en capa app).
-- Los datos biometricos del reloj son sensibles (LFPDPPP): el portal es
-- lectura-unica y el aviso de privacidad vive en /mi-asistencia/aviso-privacidad.
-- Idempotencia: _migrations (database.py) evita re-aplicar el archivo.

ALTER TABLE employees ADD COLUMN pin_hash TEXT;
ALTER TABLE employees ADD COLUMN pin_updated_at TEXT;
