# ZK-Collector Backlog — actualizado 2026-10-16 (post-Sprint 2, directiva board MYK-218)

**Estado deploy:** WebGUI http://10.0.0.16:8081 (/health 200, /attendance 200, /api/attendance 200) · Tailscale OK · Collector RUNNING (0 devices) · SMTP verificado · Coolify auto-deploy desde master.

**Regla de merge vigente (board):** P0 se construye DESDE master, ramas `fix/<p0>-<name>`, PRs <400 líneas, CI verde (ruff), review de reviewer, merge → auto-deploy. La rama feature/myk-92-dashboard-modernization está CONGELADA (material P1/P2 pendiente de split).

## Definition of Done (board policy)
done = merged en master + CI verde + verificado en deploy (10.0.0.16:8081 o zk-receiver.tail5276ec.ts.net) + review de reviewer. Evidencia reproducible: commit SHA, output real de CI, verificación contra deploy.

---

## P0 — núcleo verificable (Sprint 3)
| # | Issue | Título | Assignee | Criterio |
|---|-------|--------|----------|----------|
| P0-0 | MYK-225 | Emulador ZKTeco a master (mock/ + fixtures cherry-pick) | backend-dev | `git ls-tree -r origin/master --name-only \| grep mock/zk_emulator.py` + CI verde + /health 200 |
| P0-0-E2E | MYK-228 | Emulador en deploy: collector pollea → registros en /attendance | devops | `curl /api/attendance` devuelve registros del seed sintético; logs muestran polling |

**Nota crítica:** los issues de emulador del Sprint 2 (MYK-177/178/179/180/186/187) quedaron done con código que vive SOLO en `fix/p0-1-supervisord` (sin merge) — por eso el deploy tiene 0 devices. MYK-225 corrige eso: el código existe, falta llevarlo a master.

## P1 — módulos HR (scope del dueño)
| # | Issue | Título | Estado |
|---|-------|--------|--------|
| P1-1 | MYK-229 | Colaboradores ABC — backend (schema + CRUD + vínculo user_id) | Sprint 3, backend-dev |
| P1-1 | MYK-230 | Colaboradores ABC — frontend UI | Sprint 3, frontend-dev (blocked by MYK-229) |
| P1-2 | MYK-232 | Ausencias: vacaciones + incapacidades + permisos | backlog (Sprint 4) |
| P1-3 | MYK-233 | Motor de reglas: turnos, retardos/faltas, revisión entrada/salida estrictos | backlog (Sprint 4) |
| P1-4 | MYK-234 | Estadísticos y KPIs dashboard + export CSV/Excel | backlog (Sprint 5) |
| P1-5 | MYK-235 | Alertas de comportamiento errático | backlog (Sprint 5) |

## Backlog no-HR
| Issue | Título | Estado |
|-------|--------|--------|
| MYK-188/MYK-215 | escalation:platform — gateway no reenvía run context (workaround: REST API) | backlog, no bloqueante (directiva board) |
| — | Split del mega-PR myk-92 en PRs coherentes (config refactor / dashboard / discovery / tests) | backlog, con reviewer |
| — | Auto-discovery LAN, reportes por rango, multi-device hardening | backlog P2 |

## Cerrado en Sprint 2 (evidencia board 2026-10-16)
- P0-2 devices fuente única (PR #21), P0-3 página asistencia (fdb9023), P0-4 export CSV/Excel, P0-5 CI ruff, P0-1 supervisord, SMTP/password reset (env vars Coolify), MYK-163 diagnóstico.
