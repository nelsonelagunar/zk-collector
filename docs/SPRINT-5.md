# SPRINT 5 — Compliance LFT batch + cierre de merges (2026-10-26 → 2026-11-01)

Objetivo: (1) desatascar la cola de merges pendientes del owner, (2) cerrar el batch de
compliance LFT (centro de trabajo, retencion, export legal), (3) hardening de CI.

## Items del sprint

| Item | Asignado | Estado inicial |
|------|----------|----------------|
| MYK-427 CT-1 centro de trabajo + sello en marcada | backend-dev | todo |
| MYK-428 RT-1 politica retencion LFT 804-III | dba | in_progress |
| MYK-466 RETRO-3 A1: guard CI anti-fechas-absolutas | backend-dev | todo |
| MYK-421 sync horaria relojes + drift | backend-dev | in_progress (carryover) |
| MYK-424 export compliance formato legal | backend-dev | in_progress (carryover) |
| MYK-425 portal /mi-asistencia | frontend-dev | in_progress (carryover) |
| MYK-414/415 RBAC backend (matriz rutas, CRUD usuarios) | backend-dev | in_progress (carryover) |
| Reviews en cola: 454 (#86), 458 (#91), 446 (#78), 449 (#82/#83), 467 (#93) | reviewer | in_progress/todo |
| MYK-423 datos laborales empleado (PR #93) | dba | review en curso (MYK-467) |
| Merge gates (owner): MYK-440 #75/#76/#77 + cola | owner | pending |

## Backlog (SIN asignar — no tocar fuera de planning)

- MYK-437 constancia exportable de asistencia por colaborador
- MYK-465 escalation:platform guard de atribucion (rechaza writes PM desde runs unassigned)

## Riesgos

- Master congelado en 1ec7be1: el owner no ha mergeado; los PRs se apilan.
- Guard cross_issue_influence (MYK-465): comentarios/PATCH del PM rechazados desde runs
  unassigned — dispositions documentadas en issues de entrega hasta que la plataforma lo resuelva.
