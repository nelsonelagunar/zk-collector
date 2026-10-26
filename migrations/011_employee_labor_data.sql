-- Datos laborales del empleado: identidad y jornada (MYK-423, compliance_nomina_2027 seccion 4 item 5)
--
-- Agrega a `employees` las columnas opcionales de identidad del trabajador y
-- de jornada (LFT 58-68): curp, rfc, nss, imss_numero_seguro, tipo_jornada, turno.
-- Todas son opcionales al capturar (NULL = no capturado); no se edita la
-- migracion 002 ya aplicada (forward-only).
--
-- El CHECK a nivel SQL solo cubre longitud/enum (defensa en profundidad);
-- la validacion de FORMATO completa (CURP 18 con estructura RENAPO, RFC 12/13
-- SAT, NSS 11 digitos) vive en src/webgui/validators.py, aplicada por la API
-- y el EmployeeRepository.
--
-- Sin indices nuevos: no existe query shape que filtre por curp/rfc hoy (la
-- busqueda del listado usa LIKE sobre codigo/nombre/email/departamento y las
-- tablas son de tamano RH, cientos-miles de filas). Revisar con EXPLAIN cuando
-- EX-1 (MYK-430) junte empleados por CURP/RFC en el export legal.
-- Sin UNIQUE sobre curp/rfc: los registros legados pueden importarse con
-- duplicados pendientes de depurar; imponerlo hoy romperia la carga inicial.
--
-- Rollback documentado (SQLite >= 3.35, evaluar en staging):
--   ALTER TABLE employees DROP COLUMN curp;
--   ALTER TABLE employees DROP COLUMN rfc;
--   ALTER TABLE employees DROP COLUMN nss;
--   ALTER TABLE employees DROP COLUMN imss_numero_seguro;
--   ALTER TABLE employees DROP COLUMN tipo_jornada;
--   ALTER TABLE employees DROP COLUMN turno;
--   DELETE FROM _migrations WHERE name = '011_employee_labor_data.sql';

ALTER TABLE employees ADD COLUMN curp TEXT
    CHECK (curp IS NULL OR length(curp) = 18);

ALTER TABLE employees ADD COLUMN rfc TEXT
    CHECK (rfc IS NULL OR length(rfc) IN (12, 13));

ALTER TABLE employees ADD COLUMN nss TEXT
    CHECK (nss IS NULL OR length(nss) = 11);

ALTER TABLE employees ADD COLUMN imss_numero_seguro TEXT
    CHECK (imss_numero_seguro IS NULL OR length(imss_numero_seguro) = 11);

-- LFT 58-60: diurna (6:00-20:00), nocturna (20:00-6:00), mixta.
ALTER TABLE employees ADD COLUMN tipo_jornada TEXT
    CHECK (tipo_jornada IS NULL OR tipo_jornada IN ('diurna', 'mixta', 'nocturna'));

-- Turno libre (matutino/vespertino/nocturno/rotativo/...): texto por compania.
ALTER TABLE employees ADD COLUMN turno TEXT;
