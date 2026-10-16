# SPRINT-3 — zk-collector: Módulos HR + Emulador verificable

**Fechas**: 2026-10-16 (viernes, lanzado tras cierre Sprint 2 + directiva BOARD ddf4f9f7) → 2026-10-23
**Objetivo del sprint**: El producto pasa de "lector de asistencia" a MVP-HR verificable: emulador en deploy que produce registros sintéticos end-to-end + módulo colaboradores (ABC) + ausencias (vacaciones/incapacidades) + retardos + estadísticos + alertas email.
**Fuente**: Directiva BOARD (ddf4f9f7): SMTP resuelto en Coolify; issues MYK-170/174/184/194/216 cancelados NO se reabren; plataforma MYK-188/215 queda en backlog.

---

## Items del sprint (issues reales del board)

| # | Issue (id corto) | Título | Asignado | Criterio de salida |
|---|------------------|--------|----------|--------------------|
| 1 | 5b53c917 [S3-1] | P0-0 Emulador ZKTeco real (TCP :4370) | backend-dev | Emulador en master; collector pollea y registra; `pytest tests/integration/test_emulator_integration.py` PASS |
| 2 | 5124bdfb [P0-0-E2E] | Emulador en deploy: collector → registros sintéticos visibles | devops | `/attendance` muestra registros del emulador en prod (10.0.0.16:8081) |
| 3 | 00ab90aa [S3-2] | HR-1a Migration tabla employees | dba | Migración aplicada; FK user_id; seed funcionando |
| 4 | 82f59312 [S3-3] | HR-1b API CRUD colaboradores (/api/employees) | backend-dev | CRUD + join nombres en asistencia; tests ≥80% módulo |
| 5 | f977325b [P1-1 FE] | Colaboradores ABC — UI altas/bajas/cambios | frontend-dev | Página colaboradores operativa en WebGUI |
| 6 | 92ecd826 [HR-2] | Vacaciones: solicitudes + aprobación + saldo | backend-dev | Flujo completo con saldo de días; tests |
| 7 | 0127caaa [HR-3] | Incapacidades: registro con tipo, rango y evidencia | (ver DUPLICADOS) | Registro + validaciones; descompuesto en S3-4/5/6 |
| 8 | 6bd39cdd [HR-4] | Retardos: horarios + motor de reglas | backend-dev | Reglas generan retardos/faltas desde asistencia |
| 9 | e9a07389 [HR-5] | Estadísticos: dashboard asistencia/puntualidad/ausentismo | (ver DUPLICADOS) | Descompuesto en HR-5a (backend d00c58c9) + HR-5b (frontend 41f12100) |
| 10 | 9ecf3403 [HR-6] | Alertas email de eventos HR | (ver DUPLICADOS) | Notificación email usando SMTP prod; sin reabrir issues cancelados |
| 11 | 41e8a074 | HOTFIX `sprint-insert`: password-reset 500 en prod | backend-dev | GET /auth/forgot-password 200; reset verificado |

**Sub-tareas de descomposición ya creadas**: S3-4 (7d238415 dba medical_leaves), S3-5 (09ccfc3e backend API incapacidades), S3-6 (54961cf2 frontend incapacidades), HR-5a (d00c58c9), HR-5b (41f12100).

---

## ⚠️ DUPLICADOS a cancelar en el próximo barrido (swarm de planning)

El planning del 17:43–17:57 fue ejecutado por MÚLTIPLES runs concurrentes de coffee (swarm), produciendo series paralelas. Mapa exacto:

| Duplicado (cancelar) | Canónico (conservar) |
|----------------------|----------------------|
| adf342f9 [P0-0] cherry-pick a master | 5b53c917 [S3-1] — verificar alcance antes de cancelar |
| 356d2516 [P1-1] backend colaboradores | 82f59312 [S3-3] |
| b7f4abba [P1-2] Módulo Ausencias | 92ecd826 [HR-2] + 0127caaa [HR-3] |
| 85c1284d [P1-3] Motor de reglas | 6bd39cdd [HR-4] |
| d97e933c [P1-4] Estadísticos y KPIs | e9a07389 [HR-5] |
| 79f79b2d [HR-5] métricas (backlog) | e9a07389 [HR-5] |
| 2f21147c [P1-5] Alertas comportamiento | 9ecf3403 [HR-6] |
| 99cc199e escalation:platform (todo) | 94aebb74 (escalación activa, in_progress) |

**Reasignación pendiente (regla: el PM no retiene ingeniería)**: los parents 0127caaa, e9a07389 y 9ecf3403 quedaron asignados a coffee — reasignar al especialista (backend-dev / integrations-dev) o cerrar cuando sus sub-tareas S3-x/HR-5a/b cubran el alcance, con comentario de cierre.

---

## Definition of Done (igual que Sprint 2, endurecida)

Código mergeeado a master + tests pasando (≥80% por módulo) + code review de reviewer + QA de tester + verificación de deploy por devops. Emulador como fuente de verificación end-to-end.

---

*Generado por coffee (PM) run 930c937d — board writes bloqueados por guard de run context (bug plataforma MYK-188/215, detalle nuevo: runs manuales/on_demand rechazados, runs de assignment sí escriben). Documentado localmente como fallback sancionado.*
