# SPRINT 4 — Revision de seccion Reportes + compliance (2026-10-25 →)

Epic: MYK-403 "Revision de seccion Reportes" (asignacion directa del owner) + batch compliance.
Estado al 2026-10-26: la implementacion esta entregada casi por completo; el cierre del sprint
espera los merges del owner (master congelado en 1ec7be1, gates MYK-440).

## Items y estado (evidencia board)

| Item | Estado | Entrega |
|------|--------|---------|
| MYK-404 reportes full-width + responsive | done | PR #85, review MYK-450 done |
| MYK-405 migracion 005 razon social | done | dba |
| MYK-406 ADR RBAC | blocked | PR #74 REQUEST_CHANGES (drift); espera RBAC impl 413-416 |
| MYK-407 endpoints API tokens in/out | in_progress | backend-dev |
| MYK-408 MCP server read-only | entregado | PR #86, review MYK-454 |
| MYK-409 landing publica | done | PR #77 |
| MYK-410 research NOM jornada | done | architect |
| MYK-411 razon social WebGUI+API | done | PR #80 |
| MYK-412 RBAC migracion 005 + permissions | done | PR #76 APPROVE |
| MYK-413/414/415 RBAC backend impl | in_progress | PR #91 (413) en review MYK-458 |
| MYK-416 RBAC frontend | done | PR #90 APPROVE (MYK-457) |
| MYK-419 retencion legal >=24m (P0) | done | PR #83 (fix MYK-452 aplicado, review MYK-448) |
| MYK-420 timestamps TZ ISO-8601 | done | PR #84 |
| MYK-422 hash chain + bitacora | fix en curso | PR #81, fixes dba MYK-447, re-review MYK-462 |
| MYK-423 datos laborales empleado | PR abierto | PR #93 (entrega PM MYK-453), review MYK-467 |

## Gates pendientes del owner

- MYK-440: merge PRs #75/#76/#77 (los 3 APPROVE, card fa317fca).
- Cola de review activa: PRs #78, #80-#85, #91, #93.
