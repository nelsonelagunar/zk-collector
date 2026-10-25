# Cumplimiento 2027: registro electrónico de jornada laboral (México)

> Investigación de arquitectura (MYK-410, MYK-403 item 9). Fecha: 2026-10-25.
> Estado: **borrador para revisión** — la parte laboral está verificada contra el texto oficial
> consolidado de la LFT; la parte fiscal (nómina digital/CFDI) queda marcada como
> *parcialmente verificada* hasta confirmar reglas secundarias en DOF.

## 1. Resumen ejecutivo

La reforma laboral publicada en el **DOF el 1 de mayo de 2026** adiciona la **fracción XXXIV al
artículo 132 de la LFT**: obligación de toda persona empleadora de **registrar de manera
electrónica la jornada laboral de cada persona trabajadora**, incluyendo **horario de inicio y
finalización**, y de **proporcionarlo a la autoridad cuando se le requiera**. La STPS expedirá
las disposiciones de carácter general que determinen ámbito de aplicación y excepciones — es
esa reglamentación secundaria (esperada hacia 2027) la que fijará el detalle técnico.

zk-collector **ya captura el dato crudo** (marcaciones biometricas con entrada/salida por
colaborador), pero hoy **no cumple** los requisitos de conservación (804-III), no garantiza
integridad ni bitácora, no estampa centro de trabajo ni zona horaria en el registro, y sus
exportaciones carecen de identidad fiscal del trabajador. Se proponen **6 issues hijos** para
cerrar el gap; el timbrado de nómina digital/CFDI queda **fuera de alcance** del collector
(decisión ADR-001 abajo).

**Corrección al planteamiento original**: el texto consolidado vigente de la LFT (Última
Reforma DOF 14-05-2026, diputados.gob.mx) **no contiene** artículos "804 Bis" ni "805 Bis".
Las obligaciones nuevas viven en **132-XXXIV** (obligación) y **994-IV Bis** (sanción); los
artículos 804 y 805 conservan su texto clásico (conservación de documentos y presunción).

## 2. Marco normativo (verificado)

Fuente primaria: [LFT consolidada, Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf),
"Última Reforma DOF 14-05-2026" (PDF descargado y extraído el 2026-10-25, 457 páginas).

### 2.1 LFT art. 132, fracción XXXIV (adicionada DOF 01-05-2026)

> "Registrar de manera electrónica la jornada laboral de cada persona trabajadora, incluyendo
> el horario de inicio y finalización; así como proporcionarlo a la autoridad cuando se le
> requiera. / La Secretaría del Trabajo y Previsión Social expedirá las disposiciones de
> carácter general que determinen el ámbito de aplicación y excepción a la obligación... /
> El contenido del registro electrónico hará prueba plena si se acredita que fue acordado entre
> la persona trabajadora y empleadora."

Implicaciones de producto:
- Registro **por trabajador**, **electrónico**, con **inicio y fin** de jornada (las marcadas
  de entrada/salida de zk-collector son el insumo natural).
- Debe ser **entregable a la autoridad** → exportación auditable en formato legible.
- **Plena prueba solo si fue acordado** con el trabajador → conviene bitácora de consentimiento
  y consulta self-service del propio registro por el trabajador.
- Detalle técnico (campos mínimos, conservación exacta, formatos) queda en las **disposiciones
  generales de la STPS** (pendientes de publicación al 2026-10-25).

### 2.2 LFT art. 994, fracción IV Bis (adicionada DOF 01-05-2026)

> "De 250 a 5000 Unidades de Medida y Actualización, a la persona empleadora obligada que
> incumpla con lo dispuesto por la fracción XXXIV del artículo 132 de esta Ley."

Agravantes del art. 992 (texto vigente): multa **por cada trabajador afectado**; reincidencia
(en 2 años) **duplica** la multa. Riesgo real: 250–5000 UMA por trabajador (~9736 MXN/UMA a
2026) por cada incumplimiento.

### 2.3 LFT art. 804, fracción III — conservación

El patrón debe conservar y exhibir en juicio los **controles de asistencia** (fracc. III);
las fracciones II, III y IV se conservan **"durante el último año y un año después de que se
extinga la relación laboral"** (~24 meses tras la baja). Hoy zk-collector purga registros
sincronizados a los 30 días → **no conforme** (ver gap 3).

### 2.4 LFT art. 805 — presunción en contra

La omisión de los documentos del 804 establece **presunción de ciertos los hechos que el actor
exprese en su demanda**. Un registro no exportable/incompleto juega en contra del patrón en
litigio: la integridad del dato es un requisito probatorio, no un lujo.

### 2.5 Contexto previo: teletrabajo (art. 330 Bis / NOM-037-STPS-2023)

Desde 2023 los patrones con personal en teletrabajo ya deben llevar registro electrónico de
jornada (art. 330 Bis). La fracción 132-XXXIV generaliza la obligación a **todo** el personal.

### 2.6 Lado fiscal — nómina digital, CFDI de nómina, CHALEF (parcialmente verificado)

La agenda fiscal 2026–2027 (reforma al CFF y modificaciones al Anexo 20 de la RMF) apunta a:
**nómina digital** con pago vía transferencia a cuenta/CLABE del trabajador (CFF art. 27,
fracc. V), complemento "Nóminas Digitales" en el CFDI de nómina, y refuerzo de enforcement
fiscal penal vía el **CHALEF** (Centro de Alta Dirección para el combate al lavado de dinero
y evasiones fiscales, coordinado por la FGR con SAT/UIF).

⚠️ **Salvedad**: al 2026-10-25 no pude verificar de fuente primaria (DOF/SAT) el texto exacto
ni las fechas de obligatoriedad 2027 de estos cambios fiscales. Impacto directo para
zk-collector: **nulo como obligación del producto** (el timbrado de nómina es del sistema de
nómina/contabilidad, no del collector de asistencia), pero **sí como interoperabilidad**: las
exportaciones del collector deben poder alimentar la nómina con identidad fiscal (RFC/CURP)
y jornada por día. Acción: re-verificar cuando salgan las reglas secundarias STPS/SAT
(propuesto como criterio de aceptación en el issue de exportación).

## 3. Decisión de arquitectura

**ADR-001 (MYK-410): alcance del collector frente a la reforma.**
zk-collector será el **registro electrónico de jornada** (lado LFT 132-XXXIV): captura,
conservación, integridad, bitácora, exportación a autoridad y consulta del trabajador.
**NO** implementará timbrado de CFDI de nómina, pago vía CLABE ni cálculo de nómina digital
(lado CFF): eso pertenece al sistema de nómina del cliente o a la plataforma cloud (futuro
SaaS). Alternativa descartada: convertir zk-collector en suite de nómina — duplicaría
producto existente en el ecosistema del cliente, aleja el foco del repositorio OSS, y la
obligación del registro de jornada es autónoma y cubre exactamente el gap analizado aquí.

## 4. Gap analysis de zk-collector (evidencia file:line, master@4e7ad41)

| # | Dimensión | Estado | Evidencia | Nota |
|---|-----------|--------|-----------|------|
| 1 | Timestamp con zona horaria | ⚠️ Parcial | `src/zk_client/attendance.py:67-72` (timestamp naive del reloj del dispositivo); `src/buffer/repository.py:56-68,146-148` (DATETIME sin offset); `src/zk_client/client.py:227-264` (`get_time`/`set_time` existen pero el collector nunca los llama) | Sin normalización UTC, sin offset por dispositivo, sin detección de deriva de reloj. Mezcla de convenciones: `created_at` en UTC (SQLite `CURRENT_TIMESTAMP`) vs marcada en hora local del device |
| 2 | Centro de trabajo | ⚠️ Parcial | `src/buffer/repository.py:61` (registro guarda solo `device_ip`); `migrations/001_initial_schema.sql:6-8` (`devices.name/location/zone` texto libre); `configs/devices.example.yaml` sin campo de centro | La marcada no lleva centro de trabajo estampado; la ubicación solo se deriva por IP al consultar |
| 3 | Conservación ≥24 meses | ❌ No conforme | `src/buffer/repository.py:266-309` (`_cleanup_old_records(days=30)` purga sincronizados >30 días; tope duro de 10 000 registros borra los más viejos **aunque no estén sincronizados**); `:237-264` (registros fallidos se descartan tras 5 intentos) | 30 días + tope 10k es muy inferior a 804-III (~último año + 1 año tras baja). El buffer no es autoritativo |
| 4 | Exportaciones | ⚠️ Parcial | `src/webgui/routes/attendance.py:319-449` (CSV/XLSX: id, user_name, timestamp, status, device_ip, punch_type, synced); `src/webgui/routes/attendance_stats.py:131-141` (KPIs) | Export crudo sin employee_code, sin departamento, sin centro de trabajo, sin identidad fiscal (CURP/RFC) |
| 5 | Integridad/firma de registros | ❌ Ausente | Sin hash/sello en `attendance_records` (`repository.py:56-68`); registros mutables (`mark_as_synced` UPDATE `:223-231`) y borrables (`:281,297,394-396`) | 805 convierte la falta de registro íntegro en presunción en contra |
| 6 | Bitácora de modificaciones | ❌ Ausente | Sin tabla de auditoría en `migrations/001..004`; `sync_log` (`repository.py:104-114`) solo registra sincronizaciones | Hoy no hay endpoints de edición de asistencia (rutas GET-only, `routes/attendance.py:83-319`) — la bitácora debe existir **antes** de que los haya |
| 7 | Nómina/recibos | ➖ Fuera de alcance | grep `nomina|recibo|payroll` en `src/`, `migrations/`, `configs/`: 0 hits | Confirmado ausente; correcto según ADR-001 |
| 8 | Identidad del trabajador | ⚠️ Parcial | `migrations/002_employees.sql:5-19`: employee_code, nombre, email, depto, puesto — **sin CURP, sin RFC, sin NSS** | Los identificadores que la autoridad y la nómina esperan no existen en el modelo |

Numeración de migraciones vigente: `001`–`004` → las nuevas comienzan en `005`.

## 5. Issues hijos propuestos

Cada issue se crea como hijo de MYK-410/MYK-403 con criterios de aceptación verificables
(estándar MYK-73). IDs reales se comentan en el issue del board.

1. **TZ-1 — Sello de tiempo con zona horaria y deriva de reloj** (migration `005`):
   columnas `utc_timestamp`/`tz_offset`/`device_clock_drift` en `attendance_records`;
   el collector compara `get_time()` del dispositivo contra el servidor en cada ciclo y
   registra la deriva; UI/API muestra hora del centro de México.
   *Aceptación*: marcada en dispositivo con reloj desviado >N min genera alerta en log y
   campo `device_clock_drift`; toda exportación incluye `utc_timestamp` ISO-8601 con offset.
2. **CT-1 — Entidad centro de trabajo y sello en cada marcada** (migration `005`):
   tabla `work_centers` (nombre, RFC patrón, registro patronal IMSS, dirección) y FK
   `device.work_center_id`; `attendance_records.work_center_id` estampado al capturar.
   *Aceptación*: una marcada consultada/exportada incluye el centro de trabajo sin join por
   IP; `configs/devices.yaml` soporta `work_center` por dispositivo.
3. **RT-1 — Política de retención conforme 804-III**: retención configurable (default
   26 meses ≈ último año + 1 año tras baja + margen), tope de 10k eliminado o elevado a
   "archive-and-purge" (exportación previa al purgado), purge solo para registros archivados.
   *Aceptación*: con default, registros de hace 25 meses siguen consultables; el purga solo
   procede tras archivo exitoso (test de integración lo demuestra).
4. **IN-1 — Integridad y bitácora**: hash encadenado por registro (SHA-256 del registro
   canónico + hash previo) y tabla `audit_log` append-only (quién/cuándo/qué/antes/después)
   para cualquier UPDATE/DELETE sobre `attendance_records`; edición de asistencia solo vía
   endpoint con entrada de bitácora.
   *Aceptación*: cualquier alteración de una fila rompe la verificación de cadena (test);
   todo UPDATE/DELETE genera fila en `audit_log` (trigger + test).
5. **EX-1 — Exportación de cumplimiento y consulta del trabajador**: reporte por
   trabajador/día (entrada, salida, centro de trabajo, employee_code, CURP/RFC cuando
   existan) en CSV/XLSX + JSON, reutilizando `compute_report` (MYK-241) para no bifurcar
   cifras; endpoint self-service para que el trabajador consulte su propio registro
   (soporta "acordado entre trabajador y empleador" y el requisito de plena prueba).
   *Aceptación*: export incluye hora del centro + UTC + centro de trabajo + identidad;
   test compara dashboard vs API vs export (patrón MYK-242); criterio: re-validar campos
   contra disposiciones STPS cuando se publiquen.
6. **ID-1 — Identidad fiscal del colaborador** (migration `006`): columnas `curp`, `rfc`,
   `nss` (opcionales) en `employees` + campos en formularios WebGUI y OpenAPI.
   *Aceptación*: alta/edición persiste y valida formato CURP/RFC; export de EX-1 los incluye
   cuando existen.

## 6. Fuentes

- LFT consolidada, Última Reforma DOF 14-05-2026 — Cámara de Diputados:
  https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf (verificación local del PDF, 2026-10-25:
  arts. 132-XXXIV, 994-IV Bis, 804, 805, 992, 330 Bis).
- DOF 01-05-2026: decreto de reformas a la LFT que adiciona 132-XXXIV y 994-IV Bis.
- NOM-037-STPS-2023 (teletrabajo) y LFT 330 Bis: contexto de registro electrónico previo.
- SAT/Anexo 20 RMF / CFF 27-V: nómina digital y complemento CFDI — **parcialmente verificado**,
  pendiente de confirmación en DOF (ver §2.6).
- CHALEF (FGR/SAT/UIF): contexto de enforcement fiscal — **no verificado de fuente primaria
  en esta investigación**; sin impacto directo en el alcance del collector.
