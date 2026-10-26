# Readiness Nómina Digital SAT (monitor + export por trabajador/periodo)

> MYK-439 (arquitecto) — v1, 2026-10-26. Deriva de `docs/compliance_nomina_2027.md` §2 y §4 (fila R9, PR #79).
> **No es asesoría legal ni fiscal.** Ítems "verificado" fueron contrastados contra texto
> oficial en la fecha indicada; ítems "reportado" provienen de advisories/conocimiento de
> industry y **requieren verificación en DOF/SAT antes de comprometer alcance**.
>
> **GATE:** este documento NO autoriza implementación. Sin reglas finales publicadas en DOF,
> el export se mantiene como propuesta de schema; ningún issue de implementación del lado
> SAT debe desbloquearse desde aquí.

## 1. Reglas vigentes — estado de verificación (2026-10-26)

### 1.1 Verificado (texto oficial vigente)

| Fuente | Qué dice | Relevancia para el export |
|---|---|---|
| LFT art. 804 fracc. II–IV (consolidada, "Última Reforma DOF 14-05-2026", https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf) | El patrón conserva nómina, **controles de asistencia** y comprobantes; conservación ≥ último año + 1 año post-baja | El export es la forma exhibible del "control de asistencia" |
| LFT art. 805 | Incumplir 804 = presunción de ciertos los hechos alegados por el trabajador | La integridad/retención del export es riesgo legal, no solo feature |
| Anexo 20 vigente + complemento de nómina 1.2 (SAT, www.sat.gob.mx) | CFDI de recibo de nómina con datos del trabajador (NSS, CURP, puesto, tipo de jornada, percepciones/deducciones) | El export de asistencia NO emite CFDI: es **documentación soporte** que el patrón conserva y exhibe |

### 1.2 Reportado — esquema "Nómina Digital" (NO confirmado en reglas finales)

Estado general según advisories de industry (EY/Deloitte/KPMG y prensa fiscal, con fecha de
corte temprana) y el briefing de origen; **las fechas han variado entre versiones**:

- Sustitución/complemento del recibo de nómina CFDI por entrega **al Buzón Tributario del
  trabajador** (el trabajador consulta su nómina en el portal del SAT).
- Figura de **"Contador de Nómina Digital"** como rol/certificación en el esquema.
- Registro de asistencia como **documentación soporte** que el patrón debe conservar
  (coincide con LFT 804 fracc. III vigente, que ya obliga).
- Obligatoriedad **faseada, reportada ~2026–2027**, por tamaño de patrón; fechas no
  confirmadas en DOF a la fecha de este doc.

**Nota de verificación (2026-10-26):** desde el entorno de ejecución de este run el acceso a
sat.gob.mx y dof.gob.mx está bloqueado (HTTP 403/404) — la verificación viva de fechas
debe hacerse fuera del run. Hasta entonces, todo lo de §1.2 se trata como **hipótesis de
diseño**, no requisito.

## 2. Monitor (revisar en cada ciclo de release — owner: arquitecto)

Checklist de 5 minutos por release (o ante cada wake de este issue):

1. Buscar en DOF (https://dof.gob.mx) "nómina digital" y "reglas de carácter general CFDI de
   nómina" — ¿se publicó regla final con fecha de obligatoriedad?
2. SAT (https://www.sat.gob.mx): sección nómina/recibo de nómina digital — ¿hay nueva
   versión del Anexo 20 o del complemento de nómina con campos de asistencia/jornada?
3. RMF vigente: ¿nueva regla que mencione Buzón Tributario del trabajador o registro de
   asistencia como soporte?
4. Si algo cambió: actualizar §1 de este doc (PR), re-evaluar §3 (schema) contra el
   formato publicado y **solo entonces** proponer issue de implementación al PM.
5. Sin cambios: comentar en MYK-439 "sin cambios desde <fecha>" con la fuente revisada.

## 3. Propuesta de schema: export de asistencia por trabajador/periodo

Diseñado para ser **agregable a nómina sin acoplarse al formato SAT no final**: campos base
estables (trabajador, periodo, entradas/salidas, centro) + extensibilidad por columnas
adicionales cuando existan reglas finales. Depende de R1 (timestamps tz-aware) y R2 (centro
de trabajo) de `docs/compliance_nomina_2027.md` §3.

### 3.1 Nivel registro (una fila por trabajador/día)

| Campo | Tipo | Fuente en zk-collector | Notas |
|---|---|---|---|
| `employee_code` | string | `employees.employee_code` | clave de cruce con nómina |
| `curp` / `nss` | string? | **GAP** — `employees` no los tiene | agregar cuando la regla final los pida (hoy opcional en export) |
| `work_center_code` | string | **GAP (R2)** — tabla `work_centers` pendiente | requiere R2 |
| `date` | YYYY-MM-DD | derivado del timestamp local del centro | |
| `first_in` | ISO-8601 **con offset** | buffer (requiere R1) | primera entrada del día |
| `last_out` | ISO-8601 con offset | buffer (requiere R1) | última salida del día |
| `entries_count` / `exits_count` | int | buffer | marcas totales del día |
| `computed_hours` | decimal | derivado | horas entre first_in y last_out (aprox; el motor de reglas MYK-224 define turnos) |
| `exceptions` | string[] | derivado | p.ej. `sin_salida`, `registro_duplicado` — transparentar supuestos |

### 3.2 Nivel periodo (una fila por trabajador/periodo)

`period_start`, `period_end`, `employee_code`, `work_center_code`, `days_worked`,
`days_absent`, `days_partial`, `total_hours`, `first_in/last_out` en hora del centro.

### 3.3 Formato de entrega

- **CSV y JSON** (reusa el patrón del export de estadísticos MYK-241:
  `routes/attendance_stats.py`): CSV para intercambio con el procesador de nómina,
  JSON para integraciones. XLSX opcional después.
- Timestamps SIEMPRE ISO-8601 con offset + campo espejo en Hora del Centro de México.
- Cada export incluye `generated_at`, `period`, `work_center` y `schema_version` (empezar
  en `0.1-draft` — nunca `1.0` antes de reglas finales).
- Integridad: sha256 del contenido incluido en el archivo (conectar con R6 hash chain,
  `compliance_nomina_2027.md` §3), para que la asistencia exhibida sea demostrablemente
  igual a la capturada.

### 3.4 Qué NO incluye (por diseño, hasta reglas finales)

- Cálculo de percepciones/deducciones — eso vive en el sistema de nómina, no aquí.
- Emisión/envío de CFDI o entrega a Buzón Tributario — zk-collector aporta soporte, no
  factura. Cualquier integración de envío se diseña contra la regla publicada.
- Mapeo a campos SAT concretos (nombres de nodos Anexo 20) — se congela hasta que la
  regla final fije el formato; `schema_version` 0.x lo permite evolucionar.

## 4. Dependencias y gate de implementación

- **R1 timestamps tz-aware** y **R2 centro de trabajo** (`compliance_nomina_2027.md` §3,
  issues hijos de MYK-410): prerequisito de campos base. El export no puede salir sin ellos.
- **Implementación bloqueada** hasta que el monitor (§2) detecte reglas finales publicadas
  Y el PM apruebe el alcance. Este doc propone schema, no código.
