# Cumplimiento 2027: registro electrónico de jornada laboral (México)

> Research MYK-410 (arquitecto) — v1, 2026-10-25.
> **No es asesoría legal.** Los requisitos marcados "verificado" fueron contrastados contra fuentes
> oficiales en esta fecha; los marcados "reportado" requieren verificación en DOF/SAT antes de
> comprometer alcance de producto.

## 1. Base legal verificada (texto vigente)

Fuente: Ley Federal del Trabajo consolidada, Cámara de Diputados
(https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf, "Última Reforma DOF 14-05-2026").

**Art. 804 LFT** — el patrón tiene obligación de conservar y exhibir en juicio, entre otros:
- Fracc. II: listas de raya o nómina de personal / recibos de pagos de salarios.
- Fracc. III: **controles de asistencia**, cuando se lleven en el centro de trabajo.
- Fracc. IV: comprobantes de participación de utilidades, vacaciones, aguinaldo, primas y
  aportaciones de seguridad social.
- Conservación: los documentos de las fracciones II, III y IV deben conservarse
  **"durante el último año y un año después de que se extinga la relación laboral"**.

**Art. 805 LFT** — el incumplimiento del 804 **establece la presunción de ciertos los hechos
que el actor exprese en su demanda** respecto de tales documentos, salvo prueba en contrario.
Consecuencia práctica: perder los registros de asistencia es perder el juicio laboral.

**Verificación importante (2026-10-25):** en el texto vigente de la LFT **no existen** los
artículos 804 Bis / 804 Ter / 805 Bis citados en el briefing. La "reforma de registro
electrónico de jornada" que circuló en advisories legales corresponde a iniciativas/reportes
no incorporados al texto consolidado vigente a esta fecha. Cualquier issue que dependa de esa
reforma debe partir de la verificación del decreto en DOF (https://dof.gob.mx).

## 2. Obligaciones reportadas para 2027 (NO confirmadas en texto vigente — verificar)

| Tema | Estado | Qué se reporta | Riesgo de diseño |
|---|---|---|---|
| Reforma LFT "registro electrónico de jornada" (804 Bis/Ter) | **No verificado** | Obligación de registro electrónico de entrada/salida para patrones (>100 trabajadores según advisories), NOM por STPS en 180 días, exigibilidad faseada ~2027 | Bajo: los requisitos de producto (§3) valen igual con o sin la reforma, porque 804/805 vigentes ya obligan a conservar y exhibir controles de asistencia |
| SAT — Nómina Digital | **Anteproyecto/pendiente** | Sustitución del complemento de recibo de nómina por nómina al Buzón Tributario del trabajador; "Contador de Nómina Digital"; registro de asistencia como documentación soporte que el patrón debe conservar; obligatoriedad faseada reportada 2026–2027 (fechas han cambiado entre versiones) | Medio: definir hoy un export de asistencia "nomina-digital-ready" (campos por trabajador/periodo) sin acoplarse a un formato no final |
| **CHALEF ("Centro de Alta Dirección de la Fiscalía")** | **No verificado — premisa sin evidencia** | No se encontró ninguna fuente que confirme la existencia de "CHALEF" como instancia federal. Posible confusión con trámites estatales de fiscalías (p.ej. registro de jornada ante fiscalías estatales para giros regulados) | Alto si se diseña contra una premisa inexistente: **acción requerida del PM/usuario** — confirmar qué es CHALEF y si aplica al producto |
| Zona horaria "hora centro de México" | Reportado en el briefing | Registro de entrada/salida expresado en hora oficial | Ninguno: es buena práctica de diseño independientemente de la NOM |

Fuentes de verificación pendiente: DOF (https://dof.gob.mx), SAT (https://www.sat.gob.mx —
"recibo de nómina digital"), STPS (https://www.gob.mx/stps), Anexo 20 y RMF vigentes.

## 3. Requisitos de producto (design targets)

Derivados de la LFT vigente (804/805) + requisitos reportados para 2027:

- **R1 Timestamps con zona horaria** — capturar y almacenar con offset (UTC + zona del
  dispositivo), presentar/exportar en Hora del Centro de México por defecto.
- **R2 Centro de trabajo identificable** — entidad "centro de trabajo" (nombre, RFC,
  domicilio) ligada a dispositivos y estampada en los registros.
- **R3 Datos del trabajador** — código de empleado + identidad suficiente para inspección
  (hoy `employees`; faltan campos como NSS/CURP si la NOM los exige).
- **R4 Conservación ≥ 12 meses** — retener controles de asistencia el último año y un año
  después de la terminación; jamás purga automática < 12 meses.
- **R5 Exportaciones para inspección** — export de registros crudos por colaborador/rango
  (existe) + export "constancia" verificable (integridad demostrable).
- **R6 Integridad de registros** — cadena de hash (sha256 encadenado) o equivalente;
  detección de alteración de registros históricos.
- **R7 Bitácora de modificaciones** — append-only audit log de toda edición/borrado de
  registros de asistencia y de datos del colaborador (quién, qué, cuándo, antes/después).
- **R8 Consulta del trabajador** — self-service: el colaborador consulta sus propios
  registros (la reforma reportada lo exige; hoy solo hay usuarios administrativos).
- **R9 Readiness nómina digital** — export de asistencia agregable por periodo/trabajador
  listo para el esquema SAT cuando se publiquen reglas finales.

## 4. Gap analysis zk-collector (verificado en código, master 4e7ad41)

| Req. | Estado | Evidencia |
|---|---|---|
| R1 | **GAP crítico** | `src/zk_client/attendance.py` guarda `datetime` naive del reloj del dispositivo; `src/buffer/repository.py:146` lo serializa con `isoformat()` **sin offset**. Imposible demostrar la hora oficial ni ordenar entre dispositivos en zonas distintas. `src/core/collector.py` usa `datetime.now()` naive. |
| R2 | **PARCIAL** | `devices.location`/`zone` son texto libre (`migrations/001_initial_schema.sql`); no existe entidad centro de trabajo ni vínculo RFC/domicilio. |
| R3 | **PARCIAL** | `employees` (migrations/002_employees.sql) tiene `employee_code`, nombres, departamento, puesto — suficiente para reportes internos; faltan NSS/CURP por confirmar contra NOM. |
| R4 | **GAP crítico (destrucción activa de evidencia)** | `src/buffer/repository.py` `_cleanup_old_records(days=30)` **borra registros sincronizados > 30 días** y además purga por `max_records` el más antiguo. Esto destruye los "controles de asistencia" que el art. 804 obliga a conservar y dispara la presunción del 805. |
| R5 | **Cubierto (base)** | Export crudo CSV/XLSX con filtros en `src/webgui/routes/attendance.py:319` y export de estadísticos en `routes/attendance_stats.py:104`. Falta la capa de constancia/integridad (R6). |
| R6 | **GAP** | Sin hash chain ni firma sobre registros; `sync_attempts` muta filas (`repository.py:253`); cualquier admin del SQLite puede alterar historia sin rastro. |
| R7 | **GAP** | No existe bitácora/audit log de modificaciones (sin resultados para `audit|bitácora` en `src/`). |
| R8 | **GAP** | `users`/roles solo administrativos; no hay portal del trabajador. |
| R9 | **GAP por diseño** | `src/sync/platform.py` es sync a plataforma propia; no hay export orientado a SAT/nómina digital. |

## 5. Issues hijos propuestos (criterio de aceptación)

Creados como issues hijos de MYK-410 (ver comentario del issue para ids). Prioridad sugerida:
R4 y R1 primero (R4 es riesgo legal hoy, independiente de la reforma 2027).

1. **Retention compliant (R4)** — reemplazar `_cleanup_old_records(30d)`: retención mínima
   por defecto 12 meses + 1 año post-baja, purge opt-in y precedido de export; test que
   demuestre que no se borra registro < 12 meses con config default.
2. **Timestamps con zona horaria (R1)** — capturar offset del dispositivo, almacenar
   ISO-8601 con offset, normalizar a Hora del Centro en UI/exports; backfill de registros
   existentes documentando supuestos; tests con registros de dos zonas.
3. **Centro de trabajo (R2)** — tabla `work_centers`, mapeo device→centro, incluir centro
   en registros/export; AC: cada registro exportado identifica su centro de trabajo.
4. **Integridad + bitácora (R6+R7)** — hash chain sha256 sobre inserts y audit log
   append-only de modificaciones; AC: alterar una fila existente es detectable por
   verificación y queda registrado en bitácora.
5. **Constancia de asistencia exportable (R5+R6)** — export "constancia" por colaborador y
   rango con hash de verificación incluido; AC: la constancia se valida con un verificador
   incluido.
6. **Consulta del trabajador (R8)** — self-service autenticado con acceso solo-lectura a
   sus propios registros; AC: un usuario trabajador no puede ver registros ajenos (test).
7. **Readiness nómina digital (R9)** — research/monitor: seguir Anexo 20/RMF y definir
   export por trabajador/periodo; **bloqueado hasta reglas finales del SAT** (owner:
   arquitecto, revisar cada release).

## 6. Conclusión

zk-collector NO cumple hoy la LFT vigente (art. 804) en dos puntos críticos: purga de
asistencia a 30 días (R4) y timestamps sin zona horaria demostrable (R1). Ambos son
implementables sin esperar la NOM/reforma 2027. Los demás gaps (R2, R6–R9) convierten al
producto en "completo" para el escenario 2027 reportado, pero deben dimensionarse cuando
se confirmen las reglas finales (DOF/SAT). **CHALEF queda sin confirmar** — se requiere
respuesta del PM/usuario antes de diseñar contra esa premisa.
