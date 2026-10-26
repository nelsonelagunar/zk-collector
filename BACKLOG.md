# ZK-Collector Backlog — 2026-10-26 (post-Sprint 3, planning Sprint 4 MYK-460)

**Estado deploy:** Coolify auto-deploy desde master · WebGUI http://10.0.0.16:8081 · Tailscale zk-receiver.tail5276ec.ts.net.
**Regla de merge vigente (board):** P0 se construye DESDE master, ramas `fix/<p0>-<name>` / `feature/myk-<id>-<name>`, PRs <400 líneas, CI verde (ruff), review de reviewer (UN issue de review por PR), merge → auto-deploy.

## Definition of Done (board policy)
done = merged en master + CI verde + verificado en deploy (10.0.0.16:8081 o zk-receiver.tail5276ec.ts.net) + review de reviewer + QA tester cuando aplica. Evidencia reproducible, métricas inventadas = revocación.

---

## Sprint 4 (activo, 2026-10-26 → 10-30) — ver SPRINT-4.md (docs/sprint-3-planning@3041c17)
**Objetivo:** cierre verificable compliance jornada 2027 + seguridad/RBAC.

### En vuelo (adoptados)
| Issue | Título | Assignee |
|-------|--------|----------|
| MYK-421 | Sync horaria relojes + drift | backend-dev |
| MYK-422 | Integridad hash chain + bitácora (PR #81) | backend-dev |
| MYK-424 | Export compliance LFT 66-68 (dep MYK-427) | backend-dev |
| MYK-425 | Portal /mi-asistencia | frontend-dev |
| MYK-451 | api_auth_required JSON UI (PR #87 APPROVE) | backend-dev |
| MYK-414/415/416 | RBAC middleware + API + UI (PRs #90/#91) | backend-dev / frontend-dev |
| MYK-440 | Merge gate PRs #75/#76/#77 | reviewer |
| MYK-423 | Datos laborales CURP/RFC/NSS (PR vía MYK-453) | dba |
| MYK-430 | EX-1 export cumplimiento (contrato PR #88 done) | integrations-dev |
| MYK-408 | MCP server read-only (PR #86) | integrations-dev |

### Batch nuevo (asignado en planning 10-26)
| Issue | Título | Assignee |
|-------|--------|----------|
| MYK-427 | CT-1 centros de trabajo + sello en marcada | backend-dev |
| MYK-428 | RT-1 retención: tope 10k→archive, purga opt-in | dba |
| MYK-439 | Readiness nómina digital SAT (research) | architect |
| MYK-466 | Guardia CI anti-fechas-absolutas (RETRO-3 A1) | backend-dev |

## Backlog parqueado (SIN asignar — SCRUM: se asigna en su planning)
| Issue | Módulo | Nota |
|-------|--------|------|
| MYK-437 | Constancia exportable verificable | dep: MYK-422 mergeeado |
| MYK-222 | [HR-2] Vacaciones | |
| MYK-224 | [HR-4] Retardos: horarios + motor de reglas | |
| MYK-227 | [HR-6] Alertas comportamiento errático | |
| MYK-366 | time-bomb test_alerts (PR #68 verde, falta verdict+merge) | |
| MYK-377 | nav sections (PR #69 APPROVE, CI roto por time-bomb) | merge tras #68 |
| MYK-465 | escalation:platform guard cross_issue_influence | operator |
| MYK-463 | deploy-note MYK-451→PR #87 | |
| — | Split mega-PR myk-92 · auto-discovery LAN · multi-device | P2 |

## Cancelados por reconciliación de duplicados
- 2026-10-16: MYK-225/229/232–236 (planning swarm Sprint 3).
- 2026-10-26: MYK-426/429/431/433/434/435/436/438 — tres oleadas describieron el mismo programa compliance; cobertura canónica en 420/421/422/423/425/427/428/437 (ver SPRINT-4.md).

## Sprint 3 (cerrado 2026-10-23 — 7/7 DONE, ver SPRINT-3.md §Review)
Emulador + E2E deploy, employees migration+CRUD+UI, incapacidades, estadísticos; sprint-inserts MYK-303/363/250/Halloween verificados.
