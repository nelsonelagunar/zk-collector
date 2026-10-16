# SPRINT 3 — 2026-10-16 → 2026-10-23 (reconciliado)

**Objetivo:** E2E verificable sin hardware (emulador → collector → /attendance) funcionando en el deploy + fundación módulo colaboradores (migration + CRUD) + incapacidades descompuesto.

**Origen:** Directiva board MYK-218 (SMTP resuelto, emulador P0-0, módulos HR P1). Planning ejecutado por coffee (PM) 2026-10-16 — dos runs PM paralelos crearon sets solapados; reconciliado en este doc: se conserva el set con agentes ya despiertos (MYK-219–227, 238–242), cancelados los duplicados (MYK-225/229/232–236).

## Items comprometidos

| # | Issue | Título | Asignado | Criterio de salida |
|---|-------|--------|----------|--------------------|
| S3-1 | MYK-219 | [P0-0] Emulador ZKTeco a master | backend-dev | mock/ mergeeado a master (SHA citado), PR <400 líneas CI verde, review; /health 200 post-deploy |
| S3-2 | MYK-228 | [P0-0-E2E] Emulador en deploy → registros sintéticos en /attendance | devops (blocked by MYK-219) | curl /api/attendance devuelve registros del seed; logs polling; QA tester |
| S3-3 | MYK-220 | [HR-1a] Migration tabla employees | dba | Migration aplica limpio sobre DB existente + review + merge |
| S3-4 | MYK-221 | [HR-1b] API CRUD /api/employees + join nombres en asistencia | backend-dev (blocked by MYK-220) | CRUD + device-links + join funcionando con tests + verificado en deploy |
| S3-5 | MYK-230 | ABC colaboradores — frontend UI | frontend-dev (blocked by MYK-221) | /colaboradores opera ABC en deploy; nombre vinculado visible en /attendance |
| S3-6 | MYK-238/239/240 | Incapacidades: migration medical_leaves + API + UI | dba / backend-dev / frontend-dev | CRUD /api/medical-leaves en deploy + expediente colaborador |
| S3-7 | MYK-241/242 | Estadísticos: endpoints + dashboard | backend-dev / frontend-dev | KPIs asistencia/puntualidad renderizando datos reales del emulador |

**Intel para MYK-219:** el emulador YA EXISTE en `fix/p0-1-supervisord` (mock/zk_emulator.py, mock/attendance_seed.json, tests/fixtures/mock_device.py — 6 commits sin merge a master). Por eso el deploy tiene 0 devices. Cherry-pick sobre rama cortada de master.

## Backlog parqueado (sin asignar — SCRUM: se asigna en su planning)
- MYK-222 [HR-2] Vacaciones: solicitudes + aprobación + saldo días
- MYK-224 [HR-4] Retardos: horarios por colaborador + motor de reglas
- MYK-227 [HR-6] Alertas de comportamiento errático
- MYK-188/215 escalation:platform (no bloqueante, directiva board), split mega-PR myk-92 con reviewer

## Definition of Done (política board — endurecida)
1. Commit SHA mergeeado a master (PR con review de reviewer).
2. Output REAL de tests/CI pegado en el issue/PR — métricas inventadas = revocación del done.
3. Verificación contra deploy: http://10.0.0.16:8081 (o https://zk-receiver.tail5276ec.ts.net).
4. QA de tester cuando aplica; verificación de despliegue por devops cuando toca deploy.

## Notas del planning
1. **Hallazgo clave:** los "done" de emulador del Sprint 2 eran reales en código pero viven SOLO en `fix/p0-1-supervisord` — sin merge no hay deploy. MYK-219 lo corrige.
2. **Password reset ROTO en vivo** (MYK-231, verificado 2026-10-16): /auth/forgot-password → 500, /auth/reset-password → 404. Contradice la verificación SMTP del board; backend-dev investiga.
3. **Capacidad:** backend-dev carga MYK-219 → MYK-221 (serializado); dba MYK-220 → MYK-238; devops MYK-228 tras MYK-219; frontend-dev MYK-230/240/242 según se liberan sus blockers.
