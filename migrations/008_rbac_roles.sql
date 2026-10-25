-- RBAC: normalizacion de roles legacy (ADR-001, MYK-412)
--
-- El catalogo de roles del ADR-001 es cerrado: admin, rrhh, supervisor, auditor.
-- Todo valor de users.role fuera del catalogo (incluido el legacy 'user' y
-- NULL) se normaliza a 'auditor' (perfil de solo lectura).
--
-- Idempotente: solo UPDATE, re-ejecutable sin error y sin cambios adicionales.
-- SQLite no soporta ALTER TABLE ... ADD CONSTRAINT, por lo que el catalogo NO
-- se exige a nivel BD: la validacion de rol vive en la capa app
-- (ALLOWED_ROLES en src/webgui/permissions.py).

UPDATE users
SET role = 'auditor'
WHERE role IS NULL
   OR role NOT IN ('admin', 'rrhh', 'supervisor', 'auditor');
