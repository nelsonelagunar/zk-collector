# ZK-Collector Backlog — 2026-10-16 (post-Sprint 2, directiva board MYK-218, reconciliado)

**Estado deploy:** WebGUI http://10.0.0.16:8081 (/health 200, /attendance 200, /api/attendance 200) · Tailscale OK · Collector RUNNING (0 devices) · Coolify auto-deploy desde master.
**⚠ Password reset ROTO en vivo** (MYK-231): `/auth/forgot-password` → 500, `/auth/reset-password` → 404 (verificado 2026-10-16). Contradice la verificación SMTP del board — en investigación.

**Regla de merge vigente (board):** P0 se construye DESDE master, ramas `fix/<p0>-<name>`, PRs <400 líneas, CI verde (ruff), review de reviewer, merge → auto-deploy. Rama feature/myk-92-dashboard-modernization CONGELADA (material P1/P2 para split).

**Nota:** el emulador YA EXISTE en `fix/p0-1-supervisord` (mock/zk_emulator.py + mock/attendance_seed.json + tests/fixtures/mock_device.py, 6 commits sin merge) — MYK-219 lo lleva a master vía cherry-pick desde master.

## Definition of Done (board policy)
done = merged en master + CI verde + verificado en deploy (10.0.0.16:8081 o zk-receiver.tail5276ec.ts.net) + review de reviewer + QA tester cuando aplica. Evidencia reproducible, métricas inventadas = revocación.

---

## Sprint 3 (activo, 2026-10-16 → 10-23) — ver SPRINT-3.md
| # | Issue | Título | Assignee |
|---|-------|--------|----------|
| S3-1 | MYK-219 | [P0-0] Emulador ZKTeco a master | backend-dev |
| S3-E2E | MYK-228 | [P0-0-E2E] Emulador en deploy → registros en /attendance | devops (blocked by MYK-219) |
| S3-2 | MYK-220 | [HR-1a] Migration tabla employees | dba |
| S3-3 | MYK-221 | [HR-1b] API CRUD /api/employees + join nombres | backend-dev (blocked by MYK-220) |
| S3-4/5/6 | MYK-238/239/240 | Incapacidades: migration + API + UI | dba / backend-dev / frontend-dev |
| — | MYK-230 | ABC colaboradores — frontend UI | frontend-dev (blocked by MYK-221) |
| — | MYK-241/242 | Estadísticos: endpoints + dashboard | backend-dev / frontend-dev |

## Backlog HR (SIN asignar — espera su planning; SCRUM)
| Issue | Módulo |
|-------|--------|
| MYK-222 | [HR-2] Vacaciones: solicitudes + aprobación + saldo días |
| MYK-224 | [HR-4] Retardos: horarios + motor de reglas |
| MYK-227 | [HR-6] Alertas de comportamiento errático |

## Backlog no-HR
| Issue | Título | Estado |
|-------|--------|--------|
| MYK-231 | Password reset roto en vivo (500/404) | in_progress backend-dev |
| MYK-188/215 | escalation:platform gateway (workaround REST API) | backlog, no bloqueante |
| — | Split mega-PR myk-92 en PRs coherentes | backlog, con reviewer |
| — | Auto-discovery LAN, reportes por rango, multi-device | P2 |

## Cancelados por reconciliación de duplicados (2026-10-16)
MYK-225/229/232/233/234/235 (PM run paralelo creó set equivalente MYK-219–227; se conserva el set con agentes ya despiertos).

## Cerrado en Sprint 2 (evidencia board 2026-10-16)
P0-1 supervisord, P0-2 devices fuente única (PR #21), P0-3 asistencia (fdb9023), P0-4 export CSV/Excel, P0-5 CI ruff, SMTP secrets en Coolify, MYK-163 diagnóstico.
