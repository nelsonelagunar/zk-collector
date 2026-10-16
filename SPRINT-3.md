# SPRINT 3 — 2026-10-16 → 2026-10-23

**Objetivo:** El E2E verificable sin hardware (emulador → collector → /attendance) funcionando en el deploy + primer módulo HR (Colaboradores ABC) entregado.

**Origen:** Directiva board MYK-218 (SMTP resuelto, emulador P0-0, módulos HR P1). Planning ejecutado por coffee (PM) el 2026-10-16.

## Items comprometidos

| # | Issue | Título | Asignado | Criterio de salida |
|---|-------|--------|----------|--------------------|
| S3-1 | MYK-225 | [P0-0] Emulador ZKTeco a master (cherry-pick mock/ + fixtures desde fix/p0-1-supervisord) | backend-dev | mock/ en master, PR <400 líneas CI verde, review, /health 200 post-deploy |
| S3-2 | MYK-228 | [P0-0-E2E] Emulador en deploy: collector pollea → registros sintéticos en /attendance | devops (blocked by S3-1) | curl /api/attendance devuelve registros del seed; logs polling; QA tester |
| S3-3 | MYK-229 | [P1-1] Colaboradores ABC — backend (schema, CRUD API, vínculo user_id) | backend-dev | CRUD /api/colaboradores en deploy; nombre vinculado visible en /attendance |
| S3-4 | MYK-230 | [P1-1] Colaboradores ABC — frontend UI | frontend-dev (blocked by S3-3) | /colaboradores opera ABC en deploy; PR <400 líneas |

## Backlog parqueado (sin asignar — SCRUM: se asigna en su planning)
- MYK-232 [P1-2] Ausencias (vacaciones/incapacidades/permisos)
- MYK-233 [P1-3] Motor de reglas de asistencia (retardos/faltas/revisión estricta)
- MYK-234 [P1-4] Estadísticos y KPIs + export
- MYK-235 [P1-5] Alertas de comportamiento errático
- MYK-188/215 escalation:platform (no bloqueante), split mega-PR myk-92 con reviewer

## Notas del planning
1. **Hallazgo clave:** el emulador ya existe (mock/zk_emulator.py + seed + fixtures) en `fix/p0-1-supervisord`, pero NO está en master → no está en el deploy. Los "done" del Sprint 2 eran reales en código pero no verificables en deploy. S3-1 lo corrige con cherry-pick limpio desde master.
2. **Capacidad:** backend-dev carga S3-1 y S3-3 (S3-3 arranca cuando S3-1 esté en review). frontend-dev arranca S3-4 tras la API de S3-3. devops ejecuta S3-2 al cerrarse S3-1.
3. **DoD board:** done = merged a master + CI verde + verificado en deploy + review. El board audita con evidencia.
