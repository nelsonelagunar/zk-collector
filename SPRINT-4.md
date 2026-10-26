# SPRINT 4 — 2026-10-26 → 2026-10-30 (planning ejecutado por coffee, MYK-460)

**Objetivo:** Cierre verificable del programa **compliance jornada 2027** (NOM, MYK-410) y del hardening **seguridad/RBAC**: todo item del sprint mergeeado a master con review, CI verde y deploy verificado (10.0.0.16:8081 / zk-receiver.tail5276ec.ts.net). Review + Retro = vie 2026-10-30; planning Sprint 5 = lun 2026-11-02.

**Origen:** backlog post-Sprint 3 (RETRO-3 acciones) + analisis docs/compliance_nomina_2027.md (PR #78). Tres oleadas de issues compliance quedaron reconciliadas este planning: se conserva el set en vuelo MYK-420–425 (+451, RBAC), se promueven 4 items nuevos, se cancelan 8 duplicados.

## Items comprometidos

### A. En vuelo (adoptados al sprint — ya in_progress con agentes despiertos)
| Issue | Título | Asignado | Criterio de salida |
|-------|--------|----------|--------------------|
| MYK-421 | Sync horaria relojes ZKTeco + alerta drift (MYK-410 item 3) | backend-dev | mock con drift 5min se corrige + alerta; test pegado; merge+review |
| MYK-422 | Integridad hash chain + bitacora (MYK-410 item 4) | backend-dev | PR #81 (re-review MYK-462 ok) mergeeado + verificador en deploy |
| MYK-424 | Export compliance LFT 66-68 (MYK-410 item 6) | backend-dev | CSV 'legal' golden-file; dep: MYK-427 (centro de trabajo) |
| MYK-425 | Portal /mi-asistencia (MYK-410 item 7, LFT 132-XVII) | frontend-dev | empleado ve solo sus registros; 403 ajeno; e2e test |
| MYK-451 | api_auth_required endpoints JSON UI WebGUI | backend-dev | PR #87 (verdict APPROVE MYK-464) mergeeado + deploy verificado |
| MYK-414/415/416 | RBAC: middleware + API CRUD usuarios + UI frontend | backend-dev / frontend-dev | PRs #90/#91 reviewados y mergeeados; 403 gating visible en deploy |
| MYK-440 | Merge gate PRs #75/#76/#77 (APPROVE) | reviewer | 3 PRs mergeeados, SHA citado, CI verde |
| MYK-423 | Datos laborales CURP/RFC/NSS/tipo jornada (migra 011) | dba | PR feature/myk-423-employee-labor-data abierto (MYK-453) → review → merge |
| MYK-430 | EX-1 export cumplimiento + self-service | integrations-dev | contrato entregado (PR #88); impl segun desbloqueo — sino vuelve al backlog el vie 10-30 |
| MYK-408 | MCP server read-only para agentes IA | integrations-dev | PR #86 reviewado (MYK-454) → merge |

### B. Batch nuevo (asignado en ESTE planning — lun 10-26)
| Issue | Título | Asignado | Criterio de salida |
|-------|--------|----------|--------------------|
| MYK-427 | CT-1 Entidad centro de trabajo + sello en cada marcada | backend-dev | migration idempotente + work_center en export crudo + configs/devices.yaml; tests; PR <400 lineas |
| MYK-428 | RT-1 Retencion LFT 804-III: tope 10k → archive, purga opt-in con export previo | dba | nucleo >=730d ya done (MYK-419/PR #83); queda: tope 10k, registros fallidos, opt-in; tests |
| MYK-439 | Readiness nomina digital SAT: research + schema export propuesta | architect | docs/nomina_digital_readiness.md con fuentes DOF/SAT + propuesta schema |
| MYK-466 | [RETRO-3 A1] Guardia CI anti-fechas-absolutas en tests | backend-dev | CI rompe con fecha absoluta 2026 literal; tests migrados a relativas; AGENTS.md |

## Acciones de RETRO-3 (entran a este sprint)
1. Guardia CI anti-fechas → **MYK-466** (arriba).
2. Regla UN issue de review por PR → enforcement coffee: el PM cancela duplicados de review en el mismo turno en que los detecta (PR #69 caso). Reviews duplicados del PR #88 (MYK-456 vs MYK-459) a reconciliar.
3. Escalacion plataforma guard/gateway (99cc199e → MYK-465): sigue abierta; workaround via REST API documentado como proceso oficial del sprint. Owner: operator.

## Backlog parqueado (SIN asignar — SCRUM: se asigna en su planning)
- MYK-437 Constancia exportable verificable (dep: MYK-422 integridad mergeeada)
- MYK-222 [HR-2] Vacaciones · MYK-224 [HR-4] Retardos motor de reglas · MYK-227 [HR-6] Alertas erraticas
- MYK-366/MYK-377 merge pendiente (PR #68 verde sin verdict; PR #69 APPROVE, CI roto por time-bomb — MYK-466 lo previene a futuro)
- MYK-465 escalation guard cross_issue_influence · MYK-463 deploy-note MYK-451
- Split mega-PR myk-92 (P2) · auto-discovery LAN, multi-device (P2)

## Cancelados por reconciliacion de duplicados (2026-10-26, planning MYK-460)
MYK-426, 429, 431, 433, 434, 435, 436, 438 — tres oleadas de planning paralelo describieron el mismo programa compliance. Cobertura canonica: TZ→MYK-420(done)+421 · integridad→MYK-422 · CURP/RFC/NSS→MYK-423 · centros→MYK-427 · retencion→MYK-428 · self-service→MYK-425 · constancia→MYK-437 (parked). Mismo antipatron del planning swarm 10-16 (SPRINT-3 reconciliation).

## Definition of Done (sin cambios — politica board)
1. Commit SHA mergeeado a master (PR con review de reviewer; UN issue de review por PR).
2. Output REAL de tests/CI pegado en el issue/PR.
3. Verificado en deploy: http://10.0.0.16:8081 o https://zk-receiver.tail5276ec.ts.net.
4. QA de tester cuando aplica; verificacion de despliegue por devops cuando toca deploy.
