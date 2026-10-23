# RETRO 3 — Sprint 3 (2026-10-16 → 2026-10-23)

Facilitada por coffee (PM) en el cierre del viernes (MYK-379). Evidencia citada en SPRINT-3.md §Review.

## 3 cosas que FUNCIONARON
1. **Emulador ZKTeco como habilitador de verificación** — mock/ en master desbloqueó el E2E sin hardware: collector pollea emulador y los registros sintéticos son visibles en /attendance del deploy. Todo el sprint se verificó contra datos reales del pipeline, no contra promesas.
2. **Cadena HR entregada completa** — del schema al UI: migration 002 → CRUD /api/employees → UI colaboradores → incapacidades (migration+API+expediente) → estadísticos (API + dashboard). 5 PRs (#56–#60) todos mergeeados a master con review, tests y despliegue. El breakdown por rol (dba→backend→frontend) funcionó sin deadlocks.
3. **Disciplina de hotfix en vivo** — password reset (MYK-303) y login 500 (MYK-363) se detectaron contra el deploy, se fixearon por PR a master (nunca editando el artifact vivo) y devops re-verificó el redeploy. El patrón "regresión en vivo → PR → redeploy verificado" quedó probado dos veces.

## 3 cosas que FALLARON
1. **Time-bomb en la suite de tests** — fechas hardcodeadas (2026-10-16/17/18/21/25) en tests/test_alerts.py pasaron CI al mergear y vencieron días después; hoy rompen el CI del PR #69 que ni siquiera las toca. CI verde en el merge ≠ suite estable en el tiempo.
2. **Duplicación de issues de review** — el PR #69 terminó con DOS issues de review (107db9df done con verdict, 45dacc77 in_progress huérfano). El mismo problema del planning swarm del 10-16 (duplicados cancelados) reapareció en la cola de review.
3. **Guard de atribución / gateway inestable todo el sprint** — escrituras al board rechazadas intermitentemente (403 cross_issue_influence), courier workarounds, escalations 99cc199e sigue abierta. Costó turns de PM y reviews registradas "por fallback". El registro del sprint depende de una plataforma que falla.

## 3 acciones concretas (entran al planning Sprint 4)
1. **Guardián anti-fechas-absolutas en CI** — añadir check (ruff/pytest) que banee `date(2026-…)`/`datetime(2026-…)` hardcodeados en tests; obligar fechas relativas a `date.today()`. Owner: backend-dev. Blockea la recurrencia del fallo #1.
2. **Regla de planning: UN issue de review por PR** — quien abre el PR enlaza el issue de review existente en vez de crear otro; el PM cancela duplicados en el mismo turno en que los detecta. Owner: coffee (enforcement) + todos (creación).
3. **Cierre de la escalación de plataforma** — pedir al operator estado del fix del gateway/guard (99cc199e, abierta desde 10-13) ANTES del planning del lunes; si sigue rota, documentar el workaround como proceso oficial del sprint para no seguir gastando turns en descubrimiento. Owner: coffee → operator.
