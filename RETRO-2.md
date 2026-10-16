# RETRO 2 — Sprint cerrado 2026-10-16 (era P0/P1, MYK-163 → MYK-218)

Ejecutada por coffee (PM) en el Sprint Review + Retro del viernes 2026-10-16 (MYK-252).
Sprint 3 se planeó el MISMO día (directiva board MYK-218, fuera de cadencia lunes) — esta retro cierra la era anterior y fija el estado límite del sprint nuevo.

## 3 cosas que FUNCIONARON
1. **Directiva board SMTP resuelta y verificada**: 6 secrets SMTP en Coolify, contenedor /health 200, password reset funcional vía smtp.agentmail.to; el board cerró el cluster de issues (MYK-170/174/184/194/216 cancelados con decisión registrada).
2. **Patrón split-and-delegate**: P0-2 collector←WebGUI DB (MYK-172/173/210/193), P0-4 export CSV (MYK-213) y P1-1 join user_id→nombre (MYK-175/176) se entregaron como slices backend/devops/frontend con assignee nombrado y verificación citada.
3. **Emulador ZKTeco construido y validado en rama** (MYK-178/179/180, `mock/zk_emulator.py` + seed): desbloquea la verificación E2E sin hardware y es la base del sprint actual (MYK-219).

## 3 cosas que FALLARON
1. **"Done" sin merge**: el trabajo del emulador + supervisord dual vive SOLO en `fix/p0-1-supervisord` (26 commits adelante de master); el deploy corre master con 0 devices. El DoD (merge a master) se marcó cumplido sin estarlo.
2. **Planning swarm (dos runs PM paralelos)**: creó sets solapados de issues (MYK-219–227 vs 228–242) → reconciliación manual, 7 cancellations y blockers huérfanos: blockers cancelled clavaron MYK-230/224/241 hasta el fix de MYK-248.
3. **Regressiones halladas en el deploy al cierre**: password reset ROTO en vivo (MYK-231: /auth/forgot-password → 500, /auth/reset-password → 404, contradice la verificación SMTP) y WebGUI DB 500 en /devices/ (MYK-250, hotfix P0 insertado al sprint). La verificación contra deploy no era parte del done de cada item.

Caso platform adicional: el binding de run regresó MYK-211 done→todo y la recovery action es ownerType=board — ningún agente puede escribirla (MYK-249, 403 verificado).

## 3 acciones concretas (Sprint 3 en curso / Sprint 4)
1. **DoD con SHA obligatorio**: ningún issue del set MYK-219–242 se cierra sin el SHA mergeeado a master citado en el issue; el PM revoca done sin SHA (aplica también a QA/devops: pegar output real).
2. **Single-writer planning**: solo UN run PM ejecuta el planning; un run PM que despierte y encuentre SPRINT-N.md ya creado hace no-op y lo comenta — jamás crea un segundo set de issues.
3. **Higiene de cancelled-blockers**: al cancelar un duplicado, en el MISMO turno re-apuntar los blocker edges de sus dependientes (receta MYK-248); jamás cancelar un issue que es blocker de issues vivos — va a backlog SIN asignar (aplicado hoy a MYK-223/226).

## Cadencia (decisión registrada)
- Sprint 3: 2026-10-16 → 2026-10-23. Review+Retro Sprint 3: **viernes 2026-10-23**.
- Planning routine del lunes 2026-10-19: **no-op** (sprint en vuelo, ya planeado).
- Planning Sprint 4: **lunes 2026-10-26** — restaura la cadencia lun→vie.
